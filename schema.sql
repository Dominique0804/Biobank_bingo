-- Run once in Supabase SQL Editor. Game state is accessible only through validated RPC functions.
create extension if not exists pgcrypto;
create table if not exists public.bingo_games (
 code text primary key, host_token text not null, called int[] not null default '{}', finished boolean not null default false,
 created_at timestamptz not null default now()
);
create table if not exists public.bingo_players (
 id uuid primary key default gen_random_uuid(), game_code text not null references public.bingo_games(code) on delete cascade,
 player_token text not null, display_name text not null, card int[] not null, marked int[] not null default '{}',
 line_won boolean not null default false, full_won boolean not null default false,
 created_at timestamptz not null default now()
);
create index if not exists bingo_players_game on public.bingo_players(game_code);
alter table public.bingo_games enable row level security;
alter table public.bingo_players enable row level security;
revoke all on public.bingo_games, public.bingo_players from anon, authenticated;

create or replace function public.bingo_state(p_code text, p_host_token text default null, p_player_token text default null)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare g public.bingo_games%rowtype; p public.bingo_players%rowtype; is_host boolean; result jsonb;
begin
 select * into g from public.bingo_games where code=upper(trim(p_code));
 if not found then raise exception 'Game not found'; end if;
 is_host := p_host_token is not null and p_host_token=g.host_token;
 result:=jsonb_build_object('code',g.code,'called',g.called,'finished',g.finished,
   'players',(select count(*) from public.bingo_players where game_code=g.code),
   'winners',coalesce((select jsonb_agg(jsonb_build_object('name',display_name,'kind',case when full_won then 'Full card' else 'Line' end) order by created_at) from public.bingo_players where game_code=g.code and (line_won or full_won)),'[]'::jsonb),
   'host',is_host);
 if p_player_token is not null then
   select * into p from public.bingo_players where game_code=g.code and player_token=p_player_token;
   if found then result:=result||jsonb_build_object('player',jsonb_build_object('name',p.display_name,'card',p.card,'marked',p.marked,'line_won',p.line_won,'full_won',p.full_won)); end if;
 end if;
 return result;
end $$;

create or replace function public.bingo_create()
returns jsonb language plpgsql security definer set search_path = '' as $$
declare c text; t text; alphabet text:='ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; i int;
begin
 loop
   c:=''; for i in 1..6 loop c:=c||substr(alphabet,1+floor(random()*length(alphabet))::int,1); end loop;
   t:=replace(gen_random_uuid()::text,'-','')||replace(gen_random_uuid()::text,'-','');
   begin insert into public.bingo_games(code,host_token) values(c,t); exit;
   exception when unique_violation then null; end;
 end loop;
 return jsonb_build_object('code',c,'host_token',t);
end $$;

create or replace function public.bingo_join(p_code text,p_name text,p_player_token text)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare g public.bingo_games%rowtype; p public.bingo_players%rowtype; arr int[]; attempts int:=0;
begin
 if length(coalesce(p_player_token,''))<32 then raise exception 'Invalid player token'; end if;
 select * into g from public.bingo_games where code=upper(trim(p_code));
 if not found or g.finished then raise exception 'Game not found or ended'; end if;
 select * into p from public.bingo_players where game_code=g.code and player_token=p_player_token;
 if found then return public.bingo_state(g.code,null,p_player_token); end if;
 loop
   select array_agg(n order by random()) into arr from generate_series(0,15) n;
   exit when not exists(select 1 from public.bingo_players where game_code=g.code and card=arr);
   attempts:=attempts+1; if attempts>100 then raise exception 'Could not generate a unique card'; end if;
 end loop;
 insert into public.bingo_players(game_code,player_token,display_name,card)
 values(g.code,p_player_token,left(coalesce(nullif(trim(p_name),''),'Player'),35),arr);
 return public.bingo_state(g.code,null,p_player_token);
end $$;

create or replace function public.bingo_call(p_code text,p_host_token text,p_term int)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare g public.bingo_games%rowtype;
begin
 select * into g from public.bingo_games where code=upper(trim(p_code)) for update;
 if not found or g.host_token is distinct from p_host_token then raise exception 'Host access denied'; end if;
 if g.finished then raise exception 'Game ended'; end if;
 if p_term is null or p_term<0 or p_term>15 then raise exception 'Invalid term'; end if;
 if p_term=any(g.called) then raise exception 'Already called'; end if;
 update public.bingo_games set called=array_append(called,p_term) where code=g.code;
 return public.bingo_state(g.code,p_host_token,null);
end $$;

create or replace function public.bingo_mark(p_code text,p_player_token text,p_position int)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare p public.bingo_players%rowtype; g public.bingo_games%rowtype;
begin
 select * into g from public.bingo_games where code=upper(trim(p_code));
 if not found or g.finished then raise exception 'Game not found or ended'; end if;
 select * into p from public.bingo_players where game_code=g.code and player_token=p_player_token for update;
 if not found then raise exception 'Join first'; end if;
 if p_position is null or p_position<0 or p_position>15 then raise exception 'Invalid square'; end if;
 if p_position=any(p.marked) then
   update public.bingo_players set marked=array_remove(marked,p_position) where id=p.id;
 else
   update public.bingo_players set marked=array_append(marked,p_position) where id=p.id;
 end if;
 return public.bingo_state(g.code,null,p_player_token);
end $$;

create or replace function public.bingo_claim(p_code text,p_player_token text)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare p public.bingo_players%rowtype; g public.bingo_games%rowtype; line int[]; lines int[][]; r int; c int; i int; valid_line boolean:=false; full_card boolean:=true;
begin
 select * into g from public.bingo_games where code=upper(trim(p_code)) for update;
 if not found or g.finished then raise exception 'Game not found or ended'; end if;
 select * into p from public.bingo_players where game_code=g.code and player_token=p_player_token for update;
 if not found then raise exception 'Join first'; end if;
 for r in 0..3 loop
   line:=array[r*4,r*4+1,r*4+2,r*4+3];
   if (select bool_and(pos=any(p.marked) and p.card[pos+1]=any(g.called)) from unnest(line) pos) then valid_line:=true; end if;
 end loop;
 for c in 0..3 loop
   line:=array[c,c+4,c+8,c+12];
   if (select bool_and(pos=any(p.marked) and p.card[pos+1]=any(g.called)) from unnest(line) pos) then valid_line:=true; end if;
 end loop;
 line:=array[0,5,10,15];
 if (select bool_and(pos=any(p.marked) and p.card[pos+1]=any(g.called)) from unnest(line) pos) then valid_line:=true; end if;
 line:=array[3,6,9,12];
 if (select bool_and(pos=any(p.marked) and p.card[pos+1]=any(g.called)) from unnest(line) pos) then valid_line:=true; end if;
 for i in 0..15 loop
   if not (i=any(p.marked) and p.card[i+1]=any(g.called)) then full_card:=false; end if;
 end loop;
 if not valid_line then return jsonb_build_object('ok',false,'message','Not yet: complete a line of correctly called terms.'); end if;
 update public.bingo_players set line_won=true,full_won=(full_won or full_card) where id=p.id;
 return jsonb_build_object('ok',true,'message',case when full_card then 'Full card verified!' else 'BINGO! Line verified!' end);
end $$;

create or replace function public.bingo_finish(p_code text,p_host_token text)
returns jsonb language plpgsql security definer set search_path = '' as $$
begin
 update public.bingo_games set finished=true where code=upper(trim(p_code)) and host_token=p_host_token;
 if not found then raise exception 'Host access denied'; end if;
 return public.bingo_state(p_code,p_host_token,null);
end $$;

revoke all on function public.bingo_state(text,text,text),public.bingo_create(),public.bingo_join(text,text,text),public.bingo_call(text,text,int),public.bingo_mark(text,text,int),public.bingo_claim(text,text),public.bingo_finish(text,text) from public;
grant execute on function public.bingo_state(text,text,text),public.bingo_create(),public.bingo_join(text,text,text),public.bingo_call(text,text,int),public.bingo_mark(text,text,int),public.bingo_claim(text,text),public.bingo_finish(text,text) to anon,authenticated;
