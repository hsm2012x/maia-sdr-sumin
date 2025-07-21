# lfm.py 최종 버전

from amaranth import *
from amaranth.lib.memory import Memory
import numpy as np

class LFM(Elaboratable):
    def __init__(self, clk_freq: int, tuning_word_width=32, lut_addr_width=10, sample_width=12):
        self.CLK_FREQ = clk_freq
        self.TUNING_WORD_WIDTH = tuning_word_width
        self.LUT_ADDR_WIDTH = lut_addr_width
        self.SAMPLE_WIDTH = sample_width

        # --- AXI-Lite 제어 포트 ---
        self.reg_addr = Signal(4)
        self.reg_wdata = Signal(32)
        self.reg_wstrobe = Signal(4) # 4-byte strobe로 수정
        self.reg_rdata = Signal(32)
        
        # --- 데이터 경로 포트 (표준 스트리밍 핸드셰이크) ---
        self.valid_out = Signal()
        self.ready_in = Signal()
        self.dac_data_i = Signal(signed(sample_width))
        self.dac_data_q = Signal(signed(sample_width))

    def elaborate(self, platform):
        m = Module()

        #=================================================================
        # 1. 레지스터 및 내부 상태 신호 정의
        #=================================================================
        
        # --- AXI-Lite로 제어될 내부 레지스터들 ---
        reg_tw_min = Signal(signed(self.TUNING_WORD_WIDTH))
        reg_tw_max = Signal(signed(self.TUNING_WORD_WIDTH))
        reg_chirp_step = Signal(signed(self.TUNING_WORD_WIDTH))
        
        # --- LFM 동작 상태 신호 ---
        continuous_running = Signal() # 연속 모드 실행 상태
        timer_active = Signal()       # 1초 펄스 모드 실행 상태
        is_running = Signal()         # 최종 실행 상태 (두 모드의 OR 조합)
        
        #=================================================================
        # 2. AXI-Lite 인터페이스 로직
        #=================================================================

        # --- 쓰기 로직 ---
        # 제어 명령을 위한 1클럭 펄스 생성
        start_continuous_pulse = Signal()
        stop_continuous_pulse = Signal()
        start_1sec_pulse = Signal()

        # reg_wstrobe이 활성화되면(CPU가 쓰기 명령을 내리면)
        with m.If(self.reg_wstrobe.any()):
            with m.Switch(self.reg_addr):
                with m.Case(0x0): # 0x00: 제어 레지스터
                    m.d.sync += start_continuous_pulse.eq(self.reg_wdata[0])
                    m.d.sync += stop_continuous_pulse.eq(self.reg_wdata[1])
                    m.d.sync += start_1sec_pulse.eq(self.reg_wdata[2])
                with m.Case(0x4): # 0x04: TW_MIN
                    m.d.sync += reg_tw_min.eq(self.reg_wdata)
                with m.Case(0x8): # 0x08: TW_MAX
                    m.d.sync += reg_tw_max.eq(self.reg_wdata)
                with m.Case(0xC): # 0x0C: CHIRP_STEP
                    m.d.sync += reg_chirp_step.eq(self.reg_wdata)

        # 쓰기 명령 펄스는 다음 클럭에 자동으로 0으로 리셋
        m.d.sync += start_continuous_pulse.eq(0)
        m.d.sync += stop_continuous_pulse.eq(0)
        m.d.sync += start_1sec_pulse.eq(0)

        # --- 읽기 로직 ---
        with m.Switch(self.reg_addr):
            with m.Case(0x0): # 상태 레지스터
                m.d.comb += self.reg_rdata.eq(is_running)
            with m.Case(0x4):
                m.d.comb += self.reg_rdata.eq(reg_tw_min)
            # ... 다른 레지스터 읽기 로직 ...
            with m.Default():
                m.d.comb += self.reg_rdata.eq(0)

        #=================================================================
        # 3. LFM 제어 상태 머신 (FSM)
        #=================================================================

        # --- 1초 펄스 타이머 로직 (버그 수정) ---
        PULSE_DURATION_CYCLES = self.CLK_FREQ
        timer_counter = Signal(range(PULSE_DURATION_CYCLES))

        with m.If(start_1sec_pulse):
            m.d.sync += timer_active.eq(1)
            m.d.sync += timer_counter.eq(0)
        with m.Elif(timer_active):
            with m.If(timer_counter == PULSE_DURATION_CYCLES - 1):
                m.d.sync += timer_active.eq(0)
            with m.Else():
                m.d.sync += timer_counter.eq(timer_counter + 1)
        
        # --- 연속/펄스 모드 통합 ---
        with m.If(start_continuous_pulse):
            m.d.sync += continuous_running.eq(1)
        with m.If(stop_continuous_pulse):
            m.d.sync += continuous_running.eq(0)

        m.d.comb += is_running.eq(continuous_running | timer_active)

        #=================================================================
        # 4. LFM 파형 생성 및 데이터 경로
        #=================================================================
        
        freq_acc = Signal.like(reg_tw_min)
        phase_acc = Signal.like(reg_tw_min)

        # --- 데이터 출력 핸드셰이크 ---
        m.d.comb += self.valid_out.eq(is_running)

        # --- 상태 업데이트 (핸드셰이크 성공 시) ---
        with m.If(self.valid_out & self.ready_in):
            m.d.sync += freq_acc.eq(freq_acc + reg_chirp_step)
            with m.If(freq_acc >= reg_tw_max):
                m.d.sync += freq_acc.eq(reg_tw_min)
            m.d.sync += phase_acc.eq(phase_acc + freq_acc)
        
        with m.If(~is_running):
            m.d.sync += freq_acc.eq(reg_tw_min)

        # --- LUT 조회 및 출력 ---
        lut_size = 1 << self.LUT_ADDR_WIDTH
        sin_table_init = [int(np.sin(2 * np.pi * i / lut_size) * ((1 << (self.SAMPLE_WIDTH - 1)) - 1)) for i in range(lut_size)]
        sin_lut = Memory(shape=signed(self.SAMPLE_WIDTH), depth=lut_size, init=sin_table_init)
        m.submodules.sin_lut = sin_lut
        sin_rdport = sin_lut.read_port(domain="sync")
        cos_rdport = sin_lut.read_port(domain="sync")
        lut_address = phase_acc[-self.LUT_ADDR_WIDTH:]
        m.d.comb += [
            sin_rdport.addr.eq(lut_address),
            cos_rdport.addr.eq(lut_address + (lut_size // 4)),
            self.dac_data_i.eq(cos_rdport.data),
            self.dac_data_q.eq(sin_rdport.data),
        ]
        
        return m