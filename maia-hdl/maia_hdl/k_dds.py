def freq_to_tuning_word(freq_hz, clk_freq, tuning_word_width=32):
    """
    원하는 주파수(Hz)를 FPGA NCO의 튜닝 워드로 변환합니다.
    """
    return int(round(freq_hz * (2**tuning_word_width) / clk_freq))


# 현재 설정된 값들이 어떤 주파수에 해당하는지 역산해보기
# tw_max = 143,165,577 -> 약 1 MHz


# 이 tw_min, tw_max 값을 devmem으로 레지스터에 쓰면 됩니다.


if __name__ == '__main__':
    
    # --- 사용 예시 ---
    CLK_FREQ = 30_000_000  # maia_sdr.py에 정의된 sync 클럭 주파수
    TUNING_WORD_WIDTH = 32

    tw_max_val = 143165577
    freq_max_hz = tw_max_val * CLK_FREQ / (2**TUNING_WORD_WIDTH)
    print(f"tw_max {tw_max_val}는 약 {freq_max_hz / 1e6:.2f} MHz에 해당합니다.")

    # 새로운 주파수 설정 예시
    # 예: Chirp을 100 kHz ~ 500 kHz 범위로 설정하고 싶을 때
    tw_min = freq_to_tuning_word(100_000, CLK_FREQ, TUNING_WORD_WIDTH)
    tw_max = freq_to_tuning_word(500_000, CLK_FREQ, TUNING_WORD_WIDTH)
    test_value = freq_to_tuning_word(freq_hz = 100_000, clk_freq= 10_000_000, tuning_word_width=32)
    print(f"100 kHz -> tw_min: {tw_min}")
    print(f"500 kHz -> tw_max: {tw_max}")

    print(f"Fs = 10MHz : 100 kHz -> tw_max: {test_value}")
