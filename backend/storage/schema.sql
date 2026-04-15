CREATE TABLE IF NOT EXISTS leagues (
    league_id INTEGER PRIMARY KEY,
    code VARCHAR(8) NOT NULL,
    name VARCHAR(100) NOT NULL,
    country VARCHAR(50) NOT NULL,
    season VARCHAR(10) NOT NULL,
    UNIQUE(code, season)
);

CREATE TABLE IF NOT EXISTS teams (
    team_id INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    short_name VARCHAR(5) NOT NULL,
    crest_url VARCHAR(255),
    league_id INTEGER
);

CREATE TABLE IF NOT EXISTS players (
    player_id INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    date_of_birth DATE,
    nationality VARCHAR(50),
    position VARCHAR(5) NOT NULL,
    team_id INTEGER,
    market_value_eur BIGINT,
    contract_until DATE,
    fpl_id INTEGER,
    updated_at TIMESTAMP DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS matches (
    match_id INTEGER PRIMARY KEY,
    league_id INTEGER,
    season VARCHAR(10) NOT NULL,
    matchday INTEGER,
    kickoff TIMESTAMP NOT NULL,
    status VARCHAR(20) NOT NULL,
    home_team_id INTEGER,
    away_team_id INTEGER,
    home_score INTEGER,
    away_score INTEGER,
    home_xg DOUBLE,
    away_xg DOUBLE,
    updated_at TIMESTAMP DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS shots (
    shot_id VARCHAR(32) PRIMARY KEY,
    match_id INTEGER,
    player_id INTEGER,
    team_id INTEGER,
    minute INTEGER,
    x DOUBLE,
    y DOUBLE,
    xg DOUBLE,
    result VARCHAR(20),
    situation VARCHAR(20),
    shot_type VARCHAR(20),
    season VARCHAR(10)
);

CREATE TABLE IF NOT EXISTS player_season_stats (
    player_id INTEGER,
    season VARCHAR(10),
    league_code VARCHAR(8),
    minutes_played INTEGER,
    matches_played INTEGER,
    goals INTEGER,
    assists INTEGER,
    xg DOUBLE,
    xa DOUBLE,
    xg_per_90 DOUBLE,
    xa_per_90 DOUBLE,
    shots_per_90 DOUBLE,
    key_passes_per_90 DOUBLE,
    progressive_carries_per_90 DOUBLE,
    progressive_passes_per_90 DOUBLE,
    tackles_per_90 DOUBLE,
    interceptions_per_90 DOUBLE,
    aerials_won_per_90 DOUBLE,
    dribbles_per_90 DOUBLE,
    pass_completion_pct DOUBLE,
    updated_at TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (player_id, season, league_code)
);

CREATE TABLE IF NOT EXISTS fpl_players (
    fpl_id INTEGER PRIMARY KEY,
    player_id INTEGER,
    web_name VARCHAR(50),
    position VARCHAR(3),
    team_code INTEGER,
    team_name VARCHAR(50),
    price DOUBLE,
    total_points INTEGER,
    form DOUBLE,
    points_per_game DOUBLE,
    selected_by_pct DOUBLE,
    minutes INTEGER,
    goals_scored INTEGER,
    assists INTEGER,
    clean_sheets INTEGER,
    bonus INTEGER,
    influence DOUBLE,
    creativity DOUBLE,
    threat DOUBLE,
    ict_index DOUBLE,
    injury_status VARCHAR(20),
    injury_note VARCHAR(200),
    updated_at TIMESTAMP DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS fpl_fixtures (
    fixture_id INTEGER PRIMARY KEY,
    gameweek INTEGER NOT NULL,
    kickoff TIMESTAMP,
    home_team_code INTEGER,
    away_team_code INTEGER,
    home_difficulty INTEGER,
    away_difficulty INTEGER,
    finished BOOLEAN DEFAULT false
);

CREATE TABLE IF NOT EXISTS fpl_gameweek_history (
    fpl_id INTEGER,
    gameweek INTEGER,
    points INTEGER,
    minutes INTEGER,
    goals INTEGER,
    assists INTEGER,
    bonus INTEGER,
    bps INTEGER,
    price DOUBLE,
    selected_by_pct DOUBLE,
    PRIMARY KEY (fpl_id, gameweek)
);

CREATE TABLE IF NOT EXISTS match_predictions (
    match_id INTEGER,
    model_version VARCHAR(20),
    predicted_at TIMESTAMP DEFAULT current_timestamp,
    prob_home_win DOUBLE,
    prob_draw DOUBLE,
    prob_away_win DOUBLE,
    pred_home_goals DOUBLE,
    pred_away_goals DOUBLE,
    confidence DOUBLE,
    key_factors VARCHAR,
    score_dist VARCHAR,
    PRIMARY KEY (match_id, model_version)
);

CREATE TABLE IF NOT EXISTS fpl_projections (
    fpl_id INTEGER,
    gameweek INTEGER,
    model_version VARCHAR(20),
    projected_points DOUBLE,
    projected_at TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (fpl_id, gameweek, model_version)
);

CREATE TABLE IF NOT EXISTS player_embeddings (
    player_id INTEGER,
    season VARCHAR(10),
    feature_set VARCHAR(50),
    embedding DOUBLE[],
    umap_x DOUBLE,
    umap_y DOUBLE,
    computed_at TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (player_id, season, feature_set)
);

CREATE TABLE IF NOT EXISTS collector_runs (
    id INTEGER PRIMARY KEY,
    collector_name VARCHAR(50),
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    records_fetched INTEGER,
    status VARCHAR(20),
    error_message VARCHAR(500)
);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    coins INTEGER DEFAULT 50000,
    favorite_league VARCHAR(10),
    favorite_team_id INTEGER,
    created_at TIMESTAMP DEFAULT current_timestamp,
    last_checkin DATE,
    password_hash VARCHAR(128)
);

CREATE TABLE IF NOT EXISTS coin_transactions (
    tx_id INTEGER PRIMARY KEY,
    user_id INTEGER,
    amount INTEGER NOT NULL,
    type VARCHAR(20) NOT NULL,
    description VARCHAR(200),
    match_id INTEGER,
    created_at TIMESTAMP DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS user_bets (
    bet_id INTEGER PRIMARY KEY,
    user_id INTEGER,
    match_id INTEGER NOT NULL,
    bet_type VARCHAR(20) NOT NULL,
    amount INTEGER NOT NULL,
    odds DOUBLE NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    payout INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT current_timestamp,
    settled_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS match_events (
    event_id INTEGER PRIMARY KEY,
    match_id INTEGER,
    elapsed INTEGER,
    extra_time INTEGER,
    type VARCHAR(20),
    detail VARCHAR(50),
    player_name VARCHAR(100),
    assist_name VARCHAR(100),
    team_name VARCHAR(100),
    created_at TIMESTAMP DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS match_statistics (
    stat_id INTEGER PRIMARY KEY,
    match_id INTEGER,
    team_name VARCHAR(100),
    stat_type VARCHAR(50),
    stat_value VARCHAR(20),
    created_at TIMESTAMP DEFAULT current_timestamp
);
