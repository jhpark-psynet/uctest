# API: BASEBALL_TOTAL_QUESTION

야구 단일 경기의 종합 정보(경기/순위/상황판/문자중계/상대전적/선수/응원글/배당)를 한 번에 반환.

## 1. 호출

- **Method**: `GET`
- **URL**: `https://data.psynet.co.kr/data3V1/livescore/baseballTotalQuestion`
- **Query**:
  - `auth_key` (필수) — `.env`의 `DATA30_AUTH_KEY`
  - `game_id` (필수) — 게임 ID

예:
```
GET https://data.psynet.co.kr/data3V1/livescore/baseballTotalQuestion?auth_key={DATA30_AUTH_KEY}&game_id={GAME_ID}
```

## 2. 응답 구조

> ⚠️ **실제 응답은 한 단계 더 wrap돼 있다** (명세서 원문과 다름, 2026-05-23 실측).
> - 최상위는 `{Data: {list: {...sections}}, lastUpdated}` 구조.
> - 진짜 필드들은 `Data.list.*` 아래에 있다.
> - top-level list-valued 섹션(`team_rank` / `live_board` / `play_info` / `cheer` / `betting_info` / `my_cheer`)은 모두 `{list: [...]}` 형태로 한 번 더 wrap.
> - dict 섹션(`game_info` / `vs` / `player_info`)은 wrap 없음.
> - 필드명은 **snake_case** (명세서의 `gameInfo` 같은 camelCase는 실제 응답에는 없음).
> - `my_cheer`는 **인증된 호출일 때만 존재**. `auth_key`만 들고 호출하는 일반적인 경우엔 key 자체가 빠진다.

`Data30Client.get_baseball_total_question()`은 `Data.list`까지 자동 unwrap해서 반환. 매퍼(`uctest/data30/baseball.py`)는 inner `{list: [...]}` 패턴까지 펴서 평평한 리스트로 노출.

실제 wire shape:

```
{
  "Data": {
    "list": {
      "game_info":    {...},               # dict 직속
      "team_rank":    { "list": [...] },   # list-wrapped
      "live_board":   { "list": [{...}] }, # list-wrapped (보통 1개)
      "play_info":    { "list": [...] },   # list-wrapped
      "vs": {                              # dict 직속, inner는 모두 array
        "inning_info":     [...],
        "team_vs_history": [...],
        "team_vs":         [...],
        "high_player":     [...],
        "pitcher_starter": [...]
      },
      "player_info": {                     # dict 직속, inner는 모두 array
        "home_hitter":  [...],
        "away_hitter":  [...],
        "home_pitcher": [...],
        "away_pitcher": [...]
      },
      "cheer":        { "list": [...] },   # list-wrapped, 응원글 dict들
      "my_cheer":     { "list": [...] },   # 인증 시에만 존재
      "betting_info": { "list": [...] }    # list-wrapped
    }
  },
  "lastUpdated": "..."
}
```

논리 구조 (uctest 매퍼 출력 기준):

```
Data.list (Object)
├── game_info (Object)             # 경기 기본 정보 (명세서의 gameInfo)
├── team_rank (List)               # 팀 순위
├── live_board (List, 보통 len 1)  # 실시간 상황판
├── play_info (List)               # 문자중계 / 상황 이력
├── vs (Object)
│   ├── inning_info     (List)     # 이닝별 점수
│   ├── team_vs_history (List)     # 상대 전적·시즌 평균 (명세 "Object" 오기재)
│   ├── team_vs         (List)     # 상대 전적 raw rows
│   ├── high_player     (List)     # 주목 선수 (HR 리더 등)
│   └── pitcher_starter (List)     # 선발 투수 비교
├── player_info (Object)
│   ├── home_hitter  (List)
│   ├── away_hitter  (List)
│   ├── home_pitcher (List)
│   └── away_pitcher (List)
├── my_cheer (List, optional)      # 내 응원글 (auth 시에만)
├── cheer    (List)                # 전체 응원글 (+ is_mine)
└── betting_info (List)            # 배당·베팅
```

## 3. 필드 상세

### 3.1 game_info (명세서 원문은 `gameInfo`)

| 필드 | 타입 | 설명 |
|---|---|---|
| season_id | String | 시즌 ID |
| league_id | String | 리그 ID |
| league_name | String | 리그 이름 |
| home_team_id | String | 홈팀 ID |
| home_team_name | String | 홈팀 이름 |
| away_team_id | String | 원정팀 ID |
| away_team_name | String | 원정팀 이름 |
| match_date | String | 경기 날짜 |
| match_time | String | 경기 시간 |
| home_score | String | 홈팀 점수 |
| away_score | String | 원정팀 점수 |
| state | String | 경기 상태 코드 |
| game_state_text | String | 경기 상태 텍스트 |
| state_txt_code | String | 경기 상세 상태 코드 |
| game_state_detail_text | String | 경기 상세 상태 텍스트 |

### 3.2 team_rank (List, `{list:[...]}` wrapped)

> 실제 응답에 명세 외 필드 `wild_flag` 도 함께 옴.


| 필드 | 타입 | 설명 |
|---|---|---|
| rank | String | 순위 |
| team_id | String | 팀 ID |
| team_name | String | 팀 이름 |
| league_name | String | 리그 이름 |
| league_group_id | String | 리그 그룹 ID |
| league_group_name | String | 리그 그룹 이름 |
| division_group | String | 디비전 그룹 |
| game_count | String | 경기수 |
| win_count | String | 승리 |
| draw_count | String | 무승부 |
| loss_count | String | 패배 |
| win_rate | String | 승률 |
| games_back | String | 게임차 |
| runs_scored | String | 득점 |
| runs_allowed | String | 실점 |
| home_run_count | String | 홈런 수 |
| hit_count | String | 안타 수 |
| batting_average | String | 팀 타율 |
| bbhp_count | String | 사사구 수 |
| error_count | String | 실책 수 |
| era_rate | String | 팀 평균자책점 |

### 3.3 live_board (List, `{list:[...]}` wrapped, 보통 len 1)

| 필드 | 타입 | 설명 |
|---|---|---|
| out_count | String | 아웃 카운트 |
| strike_count | String | 스트라이크 수 |
| ball_count | String | 볼 카운트 |
| runner_status | String | 주자 상황 코드 |
| b1_player_name | String | 1루 주자 이름 (다국어 KO 우선) |
| b2_player_name | String | 2루 주자 이름 |
| b3_player_name | String | 3루 주자 이름 |
| away_attack_flag | String | 원정팀 공격/수비 플래그 (1=수비, 2=공격) |
| away_text_content | String | 원정팀 상황판 텍스트 |
| home_attack_flag | String | 홈팀 공격/수비 플래그 (1=수비, 2=공격) |
| home_text_content | String | 홈팀 상황판 텍스트 |
| scoreboard_record | String | 이닝별 점수 기록 (JSON 문자열) |
| home_team_hits | String | 홈팀 안타 합계 |
| home_team_errors | String | 홈팀 실책 합계 |
| home_team_bbhp | String | 홈팀 사사구 합계 |
| away_team_hits | String | 원정팀 안타 합계 |
| away_team_errors | String | 원정팀 실책 합계 |
| away_team_bbhp | String | 원정팀 사사구 합계 |
| info_display_type | String | 정보 표시 타입 |
| away_player_id | String | 원정팀 현재 선수 ID (타자/투수) |
| home_player_id | String | 홈팀 현재 선수 ID |
| away_batter_handedness | String | 원정팀 타자 타격 위치 (1=우타, 2=좌타) |
| home_batter_handedness | String | 홈팀 타자 타격 위치 |
| away_pitcher_handedness | String | 원정팀 투수 투구 위치 (1=우완, 2=좌완) |
| home_pitcher_handedness | String | 홈팀 투수 투구 위치 |
| batter_ab_count | String | 타수 (당일) |
| batter_hit_count | String | 타자 안타수 (당일) |
| batter_home_runs | String | 타자 홈런수 (당일) |
| batter_bb_count | String | 타자 사사구수 (당일) |
| batter_rbi | String | 타자 타점 (당일) |
| batter_so_count | String | 타자 삼진수 (당일) |
| pitcher_hits_allowed | String | 투수 피안타수 (당일) |
| pitcher_so_count | String | 투수 탈삼진 (당일) |
| pitcher_earned_runs | String | 투수 자책점 (당일) |
| pitcher_innings | String | 투수 이닝수 (당일) |
| pitcher_runs_allowed | String | 투수 실점 (당일) |
| pitch_count | String | 투구수 (0 혹은 공백이면 빈문자) |
| season_batting_average | String | 시즌 타율 (비교용) |
| season_era | String | 시즌 평균자책점 (비교용) |

### 3.4 play_info (List, `{list:[...]}` wrapped, 문자중계)

| 필드 | 타입 | 설명 |
|---|---|---|
| inning_info | String | 이닝 표기 (예: 5회초, 7회말) |
| batter_order_no | String | 타자 타순 번호 |
| sequence_number | String | 순번 |
| batter_order_number | String | 타자 타순 번호 (호환용 별칭) |
| ballcount_count | String | 볼카운트 (예: 2B 1S) |
| ilsun_check | String | 일구일순 체크 (문자중계 내부 구분) |
| batter_start_order_number | String | 타자 시작 타순 (교체 전) |
| ball_code | String | 투구 볼 종류 코드 |
| stuff_code | String | 구종 코드 |
| pitch_speed_code | String | 구속 (km/h) |
| zone_x_coordinate | String | 투구 존 X 좌표 |
| zone_y_coordinate | String | 투구 존 Y 좌표 |
| x_coordinate | String | 필드 X 좌표 |
| y_coordinate | String | 필드 Y 좌표 |
| group_x_coordinate | String | 그룹 X 좌표 |
| group_y_coordinate | String | 그룹 Y 좌표 |
| livetext_value_kr | String | 문자 중계 내용 (한국어) |
| text_style_code | String | 문자 스타일 코드 |
| batter_player_name | String | 타자 선수명 (KO) |
| pitcher_player_name | String | 투수 선수명 (KO) |
| livetext_value_en | String | 문자 중계 내용 (영어) |

### 3.5 vs.inning_info (List)

| 필드 | 타입 | 설명 |
|---|---|---|
| inning | String | 이닝 순서 (1, 2, 3 ...) |
| home_team_name | String | 홈팀 이름 (KO) |
| away_team_name | String | 원정팀 이름 (KO) |
| home_team_score | String | 홈팀 이닝 점수 (없으면 -) |
| away_team_score | String | 원정팀 이닝 점수 (없으면 -) |

### 3.6 vs.team_vs_history (List, 보통 len 1)

> 명세서 원문은 "Object"로 표기했으나 실제 응답은 길이 1짜리 array (`[{...history dict...}]`). 첫 원소가 아래 필드들을 들고 있다.

| 필드 | 타입 | 설명 |
|---|---|---|
| home_team_rank | String | 홈팀 순위 |
| away_team_rank | String | 원정팀 순위 |
| home_team_all_win_count | String | 홈팀 전체 승리 수 |
| away_team_all_win_count | String | 원정팀 전체 승리 수 |
| home_team_all_draw_count | String | 홈팀 전체 무승부 수 |
| away_team_all_draw_count | String | 원정팀 전체 무승부 수 |
| home_team_all_loss_count | String | 홈팀 전체 패배 수 |
| away_team_all_loss_count | String | 원정팀 전체 패배 수 |
| home_team_recent_5_win_count | String | 홈팀 최근 5경기 승 |
| home_team_recent_5_draw_count | String | 홈팀 최근 5경기 무 |
| home_team_recent_5_loss_count | String | 홈팀 최근 5경기 패 |
| away_team_recent_5_win_count | String | 원정팀 최근 5경기 승 |
| away_team_recent_5_draw_count | String | 원정팀 최근 5경기 무 |
| away_team_recent_5_loss_count | String | 원정팀 최근 5경기 패 |
| home_team_head_to_head_win_count | String | 홈팀 상대전적 승 |
| home_team_head_to_head_draw_count | String | 홈팀 상대전적 무 |
| home_team_head_to_head_loss_count | String | 홈팀 상대전적 패 |
| away_team_head_to_head_win_count | String | 원정팀 상대전적 승 |
| away_team_head_to_head_draw_count | String | 원정팀 상대전적 무 |
| away_team_head_to_head_loss_count | String | 원정팀 상대전적 패 |
| home_team_all_win_rate | String | 홈팀 전체 승률 |
| away_team_all_win_rate | String | 원정팀 전체 승률 |
| home_team_home_win_rate | String | 홈팀 홈경기 승률 |
| away_team_home_win_rate | String | 원정팀 홈경기 승률 |
| home_team_away_win_rate | String | 홈팀 원정경기 승률 |
| away_team_away_win_rate | String | 원정팀 원정경기 승률 |
| home_team_all_runs_scored | String | 홈팀 전체 득점 |
| home_team_all_runs_allowed | String | 홈팀 전체 실점 |
| away_team_all_runs_scored | String | 원정팀 전체 득점 |
| away_team_all_runs_allowed | String | 원정팀 전체 실점 |
| home_team_home_runs_scored | String | 홈팀 홈경기 득점 |
| home_team_home_runs_allowed | String | 홈팀 홈경기 실점 |
| away_team_home_runs_scored | String | 원정팀 홈경기 득점 |
| away_team_home_runs_allowed | String | 원정팀 홈경기 실점 |
| home_team_away_runs_scored | String | 홈팀 원정경기 득점 |
| home_team_away_runs_allowed | String | 홈팀 원정경기 실점 |
| away_team_away_runs_scored | String | 원정팀 원정경기 득점 |
| away_team_away_runs_allowed | String | 원정팀 원정경기 실점 |
| home_team_all_avg_runs_scored | String | 홈팀 전체 평균 득점 |
| home_team_all_avg_runs_allowed | String | 홈팀 전체 평균 실점 |
| away_team_all_avg_runs_scored | String | 원정팀 전체 평균 득점 |
| away_team_all_avg_runs_allowed | String | 원정팀 전체 평균 실점 |
| home_team_home_avg_runs_scored | String | 홈팀 홈경기 평균 득점 |
| home_team_home_avg_runs_allowed | String | 홈팀 홈경기 평균 실점 |
| away_team_home_avg_runs_scored | String | 원정팀 홈경기 평균 득점 |
| away_team_home_avg_runs_allowed | String | 원정팀 홈경기 평균 실점 |
| home_team_away_avg_runs_scored | String | 홈팀 원정경기 평균 득점 |
| home_team_away_avg_runs_allowed | String | 홈팀 원정경기 평균 실점 |
| away_team_away_avg_runs_scored | String | 원정팀 원정경기 평균 득점 |
| away_team_away_avg_runs_allowed | String | 원정팀 원정경기 평균 실점 |
| home_team_avg_hit_rate | String | 홈팀 경기당 평균 안타 |
| away_team_avg_hit_rate | String | 원정팀 경기당 평균 안타 |
| home_team_batting_average | String | 홈팀 팀 타율 |
| away_team_batting_average | String | 원정팀 팀 타율 |
| home_team_avg_error_rate | String | 홈팀 경기당 평균 실책 |
| away_team_avg_error_rate | String | 원정팀 경기당 평균 실책 |
| home_team_earned_run_average | String | 홈팀 평균자책점 (ERA) |
| away_team_earned_run_average | String | 원정팀 평균자책점 (ERA) |
| home_league_id | String | 홈팀 리그 ID |
| away_league_id | String | 원정팀 리그 ID |
| home_team_recent_5_win_draw_loss_list | String | 홈팀 최근 5경기 승무패 (콤마 구분) |
| away_team_recent_5_win_draw_loss_list | String | 원정팀 최근 5경기 승무패 (콤마 구분) |

### 3.6a vs.pitcher_starter (List, 보통 len 1) — 명세서에 없음

선발 투수 비교. 길이 1짜리 array, 첫 원소가 양 팀 선발 정보를 한 dict에 담고 있다.

| 필드 | 타입 | 설명 |
|---|---|---|
| home_starter_id / away_starter_id | String | 선수 ID |
| home_starter_name / away_starter_name | String | 선수명 |
| home_starter_w_cn / l_cn / s_cn | String | 시즌 승/패/세이브 |
| home_starter_era / away_starter_era | String | 시즌 평균자책점 |
| home_starter_wr / away_starter_wr | String | 시즌 승률 |
| home_starter_oavg_rt / away_starter_oavg_rt | String | 피안타율 |
| home_starter_hittype_va | String | 투구 유형 (우완/좌완/우언/좌언/양투) |
| home_starter_whip_rt / away_starter_whip_rt | String | WHIP |
| home_starter_war_rt / away_starter_war_rt | String | WAR |
| home_starter_avg_pit / away_starter_avg_pit | Number | 평균 투구수 |
| home_starter_quality_start_cn / away_starter_quality_start_cn | Number | 퀄리티 스타트 수 |
| home_starter_recently3_wln / away_starter_recently3_wln | String | 최근 3경기 결과 (예: "N,W,N") |
| home_starter_vs_wln / away_starter_vs_wln | String | 상대전적 결과 |
| home_starter_start_game_cn / away_starter_start_game_cn | Number | 선발 등판 경기수 |
| home_starter_avg_inn / away_starter_avg_inn | Number | 평균 투구 이닝 |
| home_starter_profile_yn / away_starter_profile_yn | String | 프로필 사진 여부 |
| home_starter_etc_player_id / away_starter_etc_player_id | String | KBO 선수 페이지 URL |
| home_player_img_yn / away_player_img_yn | String | 선수 이미지 여부 |

### 3.6b vs.high_player (List) — 명세서에 없음

주목 선수 (홈런 리더 등). 각 원소 = 한 선수.

| 필드 | 타입 | 설명 |
|---|---|---|
| info_type | String | 정보 타입 (예: 'H' = home run leader) |
| player_id | String | 선수 ID |
| h_a_flag | String | 'H'(홈) / 'A'(원정) |
| team_id | String | 팀 ID |
| player_name | String | 선수명 |
| hr_cn | String | 홈런 수 (info_type=H인 경우) |

### 3.6c vs.team_vs (List) — 명세서에 없음

상대 전적 raw rows. 시즌 동안의 head-to-head 경기 리스트로 추정. 일부 응답에선 빈 array(`[]`)가 올 수 있다.

### 3.7 player_info.home_hitter / away_hitter (List)

> 실제 응답에 명세 외 필드 `player_img_yn`, `webp_bo_yn`, `webp_bt_yn`, `profile_yn`, `etc_player_id`도 함께 옴 (UI 이미지 렌더용 메타).


| 필드 | 타입 | 설명 |
|---|---|---|
| home_away_flag | String | 'HOME' / 'AWAY' |
| team_id | String | 팀 ID |
| idx | String | 타자 기록 인덱스 |
| season_idx | String | 시즌 기록 인덱스 |
| sr_id | String | 시즌 기록 SR_ID |
| player_id | String | 선수 ID |
| player_name | String | 선수명 (KO 우선) |
| bat_order_no | String | 타순 번호 |
| at_bat_count | String | 타수 (AB) |
| hit_count | String | 안타 수 |
| home_run_count | String | 홈런 수 |
| rbi_count | String | 타점 |
| walk_count | String | 볼넷 |
| strikeout_count | String | 삼진 |
| batting_average | String | 시즌 타율 |
| game_count | String | 시즌 경기수 |
| stolen_base_count | String | 시즌 도루 수 |
| on_base_percentage | String | 시즌 출루율 |
| slugging_percentage | String | 시즌 장타율 |
| position | String | 포지션 |
| kor_player_flag | String | 한국인 선수 여부 |
| bat_type | String | 타격 유형 (우/좌/양) |
| bat_turn_no | String | 타석 회차 |

### 3.8 player_info.home_pitcher / away_pitcher (List)

> 실제 응답에 명세 외 필드 `player_img_yn`, `webp_bo_yn`(null 가능), `webp_bt_yn`, `profile_yn`, `etc_player_id`도 함께 옴.


| 필드 | 타입 | 설명 |
|---|---|---|
| home_away_flag | String | 'HOME' / 'AWAY' |
| team_id | String | 팀 ID |
| pitcher_no | String | 팀별 투수 등판 순서 |
| player_id | String | 선수 ID |
| player_name | String | 선수명 |
| back_no | String | 등번호 |
| result_code | String | 결과 코드 (W=승, L=패, S=세, H=홀) |
| innings_pitched | String | 투구 이닝 |
| hits_allowed | String | 피안타 수 |
| strikeout_count | String | 탈삼진 수 |
| runs_allowed | String | 실점 |
| earned_runs | String | 자책점 |
| pitch_count | String | 투구수 |
| earned_run_average | String | 시즌 평균자책점 |
| win_rate | String | 시즌 승률 |
| win_count | String | 시즌 승 |
| loss_count | String | 시즌 패 |
| save_count | String | 시즌 세이브 |
| hold_count | String | 시즌 홀드 |
| game_count | String | 시즌 등판수 |
| walk_count | String | 시즌 볼넷 수 |
| throw_hand | String | 투구 유형 (우완/좌완/우언/좌언/양투) |
| position | String | 포지션 ('P' 하드코딩) |
| kor_player_flag | String | 한국인 선수 여부 |

### 3.9 my_cheer / cheer (List)

`my_cheer`와 `cheer`는 필드가 거의 동일. `cheer`에는 `is_mine`이 추가됨.

> ⚠️ **my_cheer는 인증된 사용자 호출에서만 채워진다.** `auth_key`만 사용하는 일반 서버 호출에서는 `my_cheer` 키 자체가 응답에 없거나 빈 리스트로 온다.
> ⚠️ 실제 응답에서 각 row의 일부 필드는 String이 아닌 Number/Null로 옴 (예: `cheer_no`: Integer, `user_no`: Integer, `ai_content`: null, `rep_hit`: Integer, `betting_hit_per`: Integer 등). 표의 "String"은 명세서 원문 기준 — 실제 코드에서는 정수/Null 가능성을 가정할 것.

| 필드 | 타입 | 설명 |
|---|---|---|
| cheer_no | String | 응원글 PK |
| game_id | String | 경기 ID |
| compe | String | 종목 |
| league_id | String | 리그 ID |
| user_no | String | 작성자 USER_NO |
| user_id | String | 작성자 USER_ID |
| premium_mem_yn | String | 프리미엄 회원 여부 (정기/임시 구독) |
| content | String | 응원글 본문 ('['/']' 전각 치환) |
| ai_content | String | AI 답변 본문 |
| ai_type | String | AI 답변 타입 코드 |
| ai_name | String | AI 표시명 |
| team_id | String | 응원팀 ID |
| team_name | String | 응원팀 한글명 |
| rep_hit | String | 신고 누적 수 (5회 이상이면 사진 숨김) |
| font_color | String | 글자색 (기본 #323232) |
| photo1 | String | 사진 URL |
| to_user_id | String | 대댓글 대상 USER_ID |
| to_user_no | String | 대댓글 대상 USER_NO |
| to_user_photo1 | String | 대댓글 대상 사진 |
| cheer_country_code | String | 응원 국가 코드 |
| profile_photo | String | 프로필 사진 |
| reg_date | String | 등록일 |
| con_type | String | 연결 타입 |
| betting_state | String | 베팅 상태 (0=미참여, 1=참여중, 2=오답, 3=정답, 4=종합정답) |
| betting_hit_per | String | 적중률 |
| betting_tot_answer_cnt | String | 누적 응답수 |
| betting_today_rank | String | 오늘 랭킹 |
| cheer_type | String | 응원 타입 (NN/PN/PH/PU/FN 등) |
| photo_type | String | 사진 타입 |
| is_mine | String | (`cheer` 전용) 본인 작성 여부 (Y/N) |

### 3.10 betting_info (List, `{list:[...]}` wrapped)

| 필드 | 타입 | 설명 |
|---|---|---|
| game_id | String | 게임 코드 |
| home_bet_rate | String | 홈팀 배당률 (0/빈값이면 빈문자) |
| draw_bet_rate | String | 무승부 배당률 |
| away_bet_rate | String | 어웨이팀 배당률 |
| handicap_score | String | 핸디캡 기준점 (없으면 '0.0') |
| under_over_score | String | 언더오버 기준점 |
| game_type_name | String | 게임 타입 한글명 (승무패/핸디캡/언더오버) |
| game_type_code | String | 게임 타입 코드 (P/H/U) |
| before_home_bet_rate | String | 변경 전 홈팀 배당률 |
| before_draw_bet_rate | String | 변경 전 무승부 배당률 |
| before_away_bet_rate | String | 변경 전 어웨이팀 배당률 |
| before_handicap_score | String | 변경 전 핸디캡 기준점 |
| before_under_over_score | String | 변경 전 언더오버 기준점 |
| registered_at | String | 등록 일시 |
| game_number | String | 게임 번호 (토토 게임 번호) |
