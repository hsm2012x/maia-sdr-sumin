# lfm.py 최종 버전

from amaranth import *
from amaranth.lib.memory import Memory
import numpy as np

class LFM(Elaboratable):
    def __init__(self, clk_freq: int, tuning_word_width=32, lut_addr_width=10, sample_width=12):
        # --- 파라미터 ---
        self.CLK_FREQ = clk_freq
        self.TUNING_WORD_WIDTH = tuning_word_width
        self.LUT_ADDR_WIDTH = lut_addr_width
        self.SAMPLE_WIDTH = sample_width

        # --- AXI-Lite 제어 포트 ---
        self.reg_addr = Signal(4)
        self.reg_wdata = Signal(32)
        self.reg_wstrobe = Signal()
        self.reg_rdata = Signal(32)
        
        # --- 데이터 경로 포트 (표준 스트리밍 핸드셰이크) ---
        self.valid_out = Signal() # LFM이 "보낼 데이터가 유효하다"고 알리는 신호
        self.ready_in = Signal()  # 외부에서 "데이터를 받을 준비가 됐다"고 알려주는 신호

        self.dac_data_i = Signal(signed(sample_width))
        self.dac_data_q = Signal(signed(sample_width))

    def elaborate(self, platform):
        m = Module()

        # --- 내부 신호 및 레지스터 ---
        # 제어/상태 레지스터
        reg_control = Signal(32)       # Start, Stop, Mode 등
        reg_status = Signal(32, reset=0) # is_running, timer_active
        is_running = reg_status[0]
        timer_active = reg_status[1]
        
        # LFM 파라미터 레지스터
        reg_tw_min = Signal(signed(self.TUNING_WORD_WIDTH))
        reg_tw_max = Signal(signed(self.TUNING_WORD_WIDTH))
        reg_chirp_step = Signal(signed(self.TUNING_WORD_WIDTH))

        # 1초 펄스 타이머용 카운터
        PULSE_DURATION_CYCLES = self.CLK_FREQ # 1초 = 클럭 주파수 만큼의 사이클
        timer_counter = Signal(range(PULSE_DURATION_CYCLES))

        # --- AXI-Lite 쓰기 로직 ---
        with m.If(self.reg_wstrobe):
            with m.Switch(self.reg_addr):
                with m.Case(0x00): # 0x00: 제어 레지스터
                    m.d.sync += reg_control.eq(self.reg_wdata)
                with m.Case(0x04): # 0x04: TW_MIN
                    m.d.sync += reg_tw_min.eq(self.reg_wdata)
                with m.Case(0x08): # 0x08: TW_MAX
                    m.d.sync += reg_tw_max.eq(self.reg_wdata)
                with m.Case(0x0C): # 0x0C: CHIRP_STEP
                    m.d.sync += reg_chirp_step.eq(self.reg_wdata)

        # --- AXI-Lite 읽기 로직 ---
        with m.Switch(self.reg_addr):
            with m.Case(0x00):
                m.d.comb += self.reg_rdata.eq(reg_status) # 상태 레지스터 읽기
            with m.Case(0x04):
                m.d.comb += self.reg_rdata.eq(reg_tw_min)
            # ... (다른 레지스터 읽기 로직 추가 가능) ...
            with m.Default():
                m.d.comb += self.reg_rdata.eq(0)

        # --- 1초 펄스 타이머 로직 ---
        start_1sec_pulse = reg_control[1]
        with m.If(start_1sec_pulse): # "1초 시작" 명령이 들어오면
            m.d.sync += timer_active.eq(1)
            m.d.sync += timer_counter.eq(0)
        with m.Elif(timer_active): # 타이머가 동작 중일 때
            with m.If(timer_counter == PULSE_DURATION_CYCLES - 1):
                m.d.sync += timer_active.eq(0) # 1초가 다 되면 자동으로 끔
        with m.Else:
                m.d.sync += timer_counter.eq(timer_counter + 1)
        
        # --- LFM 실행 상태 결정 로직 ---
        start_continuous = reg_control[0]
        # 펄스 모드가 활성화되었거나, 연속 모드 시작 명령이 들어오면 is_running=1
        m.d.comb += is_running.eq(timer_active | start_continuous)

        # --- LFM 핵심 로직: 주파수/위상 누산기 ---
        freq_acc = Signal.like(reg_tw_min)
        phase_acc = Signal.like(reg_tw_min)

        # '데이터 유효'하고 '받을 준비'가 모두 되었을 때만 상태 업데이트
        with m.If(self.valid_out & self.ready_in):
            m.d.sync += freq_acc.eq(freq_acc + reg_chirp_step)
            with m.If(freq_acc >= reg_tw_max):
                m.d.sync += freq_acc.eq(reg_tw_min)
            m.d.sync += phase_acc.eq(phase_acc + freq_acc)
        
        with m.If(~is_running):
            m.d.sync += freq_acc.eq(reg_tw_min)

        # --- 데이터 출력 핸드셰이크 ---
        # LFM이 실행 중일 때만 데이터가 유효하다고 알림
        m.d.comb += self.valid_out.eq(is_running)

        # --- LUT 로직 ---
        lut_size = 1 << self.LUT_ADDR_WIDTH
        sin_table_init = [int(np.sin(2 * np.pi * i / lut_size) * ((1 << (self.sample_width - 1)) - 1)) for i in range(lut_size)]
        sin_lut = Memory(shape=signed(self.sample_width), depth=lut_size, init=sin_table_init)
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