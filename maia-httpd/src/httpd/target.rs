// src/httpd/target.rs

use super::json_error::JsonError;
use crate::app::AppState;
use anyhow::Result;
use axum::{extract::State, Json};
use maia_json::{PatchTarget, Target};

const SPEED_OF_LIGHT: f64 = 299_792_458.0;

// 도플러 계산 헬퍼 함수
fn calculate_doppler(rx_freq: u64, velocity: f64) -> u64 {
    let rx_f64 = rx_freq as f64;
    // 왕복 도플러: f_tx = f_rx * (1 - 2v/c)
    let factor = 1.0 - (2.0 * velocity / SPEED_OF_LIGHT);
    // 음수 주파수 방지 (.max(0.0))
    (rx_f64 * factor).max(0.0).round() as u64
}

// 내부 헬퍼 함수: AppState에서 정보를 읽어 Target 구조체 반환
pub async fn target_json(state: &AppState) -> Result<Target> {
    // 1. AD9361에서 현재 RX 주파수 읽기
    let rx_freq = state
        .ad9361()
        .lock()
        .await
        .get_rx_lo_frequency()
        .await?; // anyhow가 에러 처리

    // 2. AppState 메모리에서 현재 설정된 속도 읽기
    let velocity = *state.target_velocity().lock().unwrap();

    // 3. 도플러 주파수 계산
    let recommended_tx_freq = calculate_doppler(rx_freq, velocity);

    // 4. 결과 반환 (이 부분이 ... 으로 되어 있어서 에러가 났었습니다)
    Ok(Target {
        velocity,
        recommended_tx_frequency: recommended_tx_freq,
    })
}

// GET /api/target 핸들러
pub async fn get_target(State(state): State<AppState>) -> Result<Json<Target>, JsonError> {
    target_json(&state)
        .await
        .map_err(JsonError::server_error) // anyhow::Error -> JsonError 변환
        .map(Json)
}

// PATCH /api/target 핸들러 (속도 설정용)
pub async fn patch_target(
    State(state): State<AppState>,
    Json(patch): Json<PatchTarget>,
) -> Result<Json<Target>, JsonError> {
    if let Some(vel) = patch.velocity {
        *state.target_velocity().lock().unwrap() = vel;
    }
    // 업데이트 후 현재 상태 반환
    get_target(State(state)).await
}