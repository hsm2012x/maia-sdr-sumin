# test_dds.py (가이드 기반 최종 버전)

import numpy as np
import matplotlib.pyplot as plt

from amaranth import *
from amaranth.sim import Simulator
from amaranth.lib.memory import Memory
# 파일 상단
from amaranth.sim import Simulator, Tick
# 1. 테스트 대상 모듈(DDS) 정의 (버그 수정 및 ports() 메소드 추가)
class DDS(Elaboratable):
    def __init__(self, *, tuning_word_0, tuning_word_1, tuning_word_2, hop_rate,
                 tuning_word_width=32, lut_addr_width=10, sample_width=12):
        self.tw0 = C(tuning_word_0, signed(tuning_word_width))
        self.tw1 = C(tuning_word_1, signed(tuning_word_width))
        self.tw2 = C(tuning_word_2, signed(tuning_word_width))
        self.hop_rate = C(hop_rate, range(hop_rate + 1))
        
        # 포트 정의
        self.ready_in = Signal()
        self.dac_data_i = Signal(signed(sample_width))
        self.dac_data_q = Signal(signed(sample_width))
        self.hop_state_out = Signal(2) # 디버깅용 상태 출력

        # 내부 변수
        self.tuning_word_width = tuning_word_width
        self.lut_addr_width = lut_addr_width
        self.sample_width = sample_width

    def ports(self):
        """시뮬레이션 VCD 파일에 포함할 포트 목록을 반환합니다."""
        return [
            self.ready_in,
            self.dac_data_i,
            self.dac_data_q,
            self.hop_state_out,
        ]

    def elaborate(self, platform):
        m = Module()
        current_tuning_word = Signal.like(self.tw0)
        hop_counter = Signal.like(self.hop_rate)
        hop_state = Signal(2)

        with m.If(self.ready_in):
            with m.If(hop_counter >= self.hop_rate):
                m.d.sync += hop_counter.eq(0)
                m.d.sync += hop_state.eq(hop_state + 1)
            with m.Else():
                m.d.sync += hop_counter.eq(hop_counter + 1)

        with m.Switch(hop_state):
            with m.Case(0): m.d.comb += current_tuning_word.eq(self.tw0)
            with m.Case(1): m.d.comb += current_tuning_word.eq(self.tw1)
            with m.Case(2): m.d.comb += current_tuning_word.eq(self.tw2)
            with m.Default(): m.d.comb += current_tuning_word.eq(self.tw0)
        
        phase_acc = Signal(self.tuning_word_width)
        with m.If(self.ready_in):
            m.d.sync += phase_acc.eq(phase_acc + current_tuning_word)

        lut_size = 1 << self.lut_addr_width
        sin_table_init = [int(np.sin(2 * np.pi * i / lut_size) * ((1 << (self.sample_width - 1)) - 1)) for i in range(lut_size)]
        sin_lut = Memory(shape=signed(self.sample_width), depth=lut_size, init=sin_table_init)
        m.submodules.sin_lut = sin_lut
        
        sin_rdport = sin_lut.read_port(domain="sync")
        cos_rdport = sin_lut.read_port(domain="sync")
        
        lut_address = phase_acc[-self.lut_addr_width:]
        m.d.comb += [
            sin_rdport.addr.eq(lut_address),
            cos_rdport.addr.eq(lut_address + (lut_size // 4)),
            self.dac_data_i.eq(cos_rdport.data),
            self.dac_data_q.eq(sin_rdport.data),
            self.hop_state_out.eq(hop_state)
        ]
        return m

# test_dds.py의 메인 실행 블록 수정

if __name__ == '__main__':
    # DDS 모듈 인스턴스화
    dds_module = DDS(
        tuning_word_0=-55924053,
        tuning_word_1=27962026,
        tuning_word_2=55924053,
        hop_rate=1023,
        sample_width=12
    )

    # 시뮬레이터를 위한 최상위 모듈 생성
    m = Module()
    m.submodules.dds = dds_module

    # 시뮬레이터 생성
    sim = Simulator(m)
    sim.add_clock(1e-8)  # 'sync' 도메인에 100MHz 클럭 추가

    # 테스트벤치 프로세스 정의
    i_samples = []
    q_samples = []
    def bench():
        yield dds_module.ready_in.eq(1)
        for _ in range(80000):
            # <<< 핵심 수정: yield를 yield Tick()으로 변경 >>>
            yield Tick()
            i_samples.append((yield dds_module.dac_data_i))
            q_samples.append((yield dds_module.dac_data_q))

    # <<< 오류 수정 1: add_sync_process 대신 add_process 사용 >>>
    sim.add_process(bench)

    # 시뮬레이션 실행 및 VCD 파일 생성
    with sim.write_vcd("test.vcd", "test.gtkw", traces=dds_module.ports()):
        print("시뮬레이션 실행 중...")
        # <<< 오류 수정 2: sim.run()을 with 블록 안에서 호출 >>>
        sim.run()

    # --- 시뮬레이션 완료 후, matplotlib으로 결과 시각화 ---
    print("시뮬레이션 완료. VCD 파일 생성됨. 총 샘플 수:", len(i_samples))

    # 샘플이 없을 경우 그래프 그리기 중단
    if not i_samples:
        print("수집된 샘플이 없어 그래프를 그릴 수 없습니다.")
    else:
        complex_signal = np.array(i_samples) + 1j * np.array(q_samples)
        fig, axs = plt.subplots(2, 1, figsize=(12, 8))
        axs[0].set_title("Time Domain Waveform (first 2000 samples)")
        axs[0].plot(i_samples[:8000], label="I component")
        axs[0].plot(q_samples[:8000], label="Q component")
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
