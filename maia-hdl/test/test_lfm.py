# test_dds.py (가이드 기반 최종 버전)

import numpy as np
import matplotlib.pyplot as plt

from amaranth import *
from amaranth.sim import Simulator
from amaranth.lib.memory import Memory
# 파일 상단
from amaranth.sim import Simulator, Tick
from lfm import LFM

if __name__ == '__main__':
    # <<< 핵심 수정: LFM 클래스를 인자 없이 생성합니다 >>>
    # LFM(처프) 모듈은 파라미터를 내부에서 상수로 정의하므로 인자가 필요 없습니다.
    lfm_module = LFM()

    # 시뮬레이터를 위한 최상위 모듈 생성
    m = Module()
    m.submodules.lfm = lfm_module

    # 시뮬레이터 생성
    sim = Simulator(m)
    sim.add_clock(1e-8)  # 'sync' 도메인에 100MHz 클럭 추가

    # 테스트벤치 프로세스 정의
    i_samples = []
    q_samples = []
    def bench():
        yield lfm_module.ready_in.eq(1)
        # 4096 * 4 = 16384 사이클만 시뮬레이션하여 4번의 처프 주기 확인
        for _ in range(16384): 
            yield Tick()
            i_samples.append((yield lfm_module.dac_data_i))
            q_samples.append((yield lfm_module.dac_data_q))

    sim.add_process(bench)

    # 시뮬레이션 실행 및 VCD 파일 생성
    with sim.write_vcd("test.vcd", "test.gtkw", traces=lfm_module.ports()):
        print("시뮬레이션 실행 중...")
        sim.run()

    # --- 시뮬레이션 완료 후, matplotlib으로 결과 시각화 ---
    print("시뮬레이션 완료. VCD 파일 생성됨. 총 샘플 수:", len(i_samples))

    if not i_samples:
        print("수집된 샘플이 없어 그래프를 그릴 수 없습니다.")
    else:
        # ... (이하 그래프 그리는 코드는 동일)
        complex_signal = np.array(i_samples) + 1j * np.array(q_samples)
        fig, axs = plt.subplots(2, 1, figsize=(12, 8))

        axs[0].set_title("Time Domain Chirp Waveform")
        axs[0].plot(i_samples, label="I component")
        axs[0].plot(q_samples, label="Q component")
        axs[0].set_xlabel("Sample Number")
        axs[0].set_ylabel("Amplitude")
        axs[0].grid(True)
        axs[0].legend()

        axs[1].set_title("Frequency Domain (Power Spectral Density)")
        axs[1].psd(complex_signal, NFFT=1024, Fs=30.72e6)
        axs[1].set_xlabel("Frequency (Hz)")
        axs[1].set_ylabel("Power/Frequency (dB/Hz)")
        
        plt.tight_layout()
        plt.show()
