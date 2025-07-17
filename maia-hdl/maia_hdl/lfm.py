# lfm.py 파일 수정

from amaranth import *
from amaranth.lib.memory import Memory
import numpy as np

class LFM(Elaboratable):
    def __init__(self, tuning_word_width=32, lut_addr_width=10, sample_width=12):
        # --- 제어/상태 레지스터 포트 ---
        # 이 포트들은 나중에 MaiaSDR 모듈 내부의 레지스터 블록에 연결됩니다.
        self.reg_addr = Signal(4)
        self.reg_wdata = Signal(32)
        self.reg_wstrobe = Signal() # 쓰기 활성화
        self.reg_rdata = Signal(32)
        
        # --- 데이터 경로 포트 ---
        self.dac_enable_in = Signal()
        self.dac_valid_in = Signal()
        self.dac_data_i = Signal(signed(sample_width))
        self.dac_data_q = Signal(signed(sample_width))

        # 내부 변수들...
        self.tuning_word_width = tuning_word_width
        self.lut_addr_width = lut_addr_width
        self.sample_width = sample_width

    def elaborate(self, platform):
        m = Module()

        # --- 제어 및 상태 레지스터용 내부 신호 ---
        is_running = Signal(reset=0)
        tw_min = Signal.like(C(0, signed(self.tuning_word_width)))
        tw_max = Signal.like(C(0, signed(self.tuning_word_width)))
        chirp_step = Signal.like(C(0, signed(self.tuning_word_width)))
        valid_counter = Signal(32)

        # --- AXI-Lite 쓰기 동작 처리 ---
        with m.If(self.reg_wstrobe):
            with m.Switch(self.reg_addr):
                with m.Case(0x00): # 제어 레지스터
                    with m.If(self.reg_wdata[0]): # Start
                        m.d.sync += is_running.eq(1)
                    with m.If(self.reg_wdata[1]): # Stop
                        m.d.sync += is_running.eq(0)
                with m.Case(0x04): # TW_MIN
                    m.d.sync += tw_min.eq(self.reg_wdata)
                with m.Case(0x08): # TW_MAX
                    m.d.sync += tw_max.eq(self.reg_wdata)
                with m.Case(0x0C): # CHIRP_STEP
                    m.d.sync += chirp_step.eq(self.reg_wdata)

        # --- AXI-Lite 읽기 동작 처리 ---
        with m.Switch(self.reg_addr):
            with m.Case(0x00): # 상태 레지스터
                m.d.comb += self.reg_rdata.eq(is_running)
            with m.Case(0x04): # TW_MIN
                m.d.comb += self.reg_rdata.eq(tw_min)
            # ... TW_MAX, CHIRP_STEP 읽기 로직 추가 가능 ...
            with m.Case(0x10): # Valid 카운터
                m.d.comb += self.reg_rdata.eq(valid_counter)
            with m.Default():
                m.d.comb += self.reg_rdata.eq(0)

        # --- LFM/위상 누산기 로직 ---
        freq_acc = Signal(signed(self.tuning_word_width), reset=0)
        phase_acc = Signal(self.tuning_word_width)

        with m.If(is_running & self.dac_enable_in & self.dac_valid_in):
            m.d.sync += freq_acc.eq(freq_acc + chirp_step)
            with m.If(freq_acc >= tw_max):
                m.d.sync += freq_acc.eq(tw_min)
            
            m.d.sync += phase_acc.eq(phase_acc + freq_acc)
            m.d.sync += valid_counter.eq(valid_counter + 1)
        
        with m.If(~is_running):
            m.d.sync += freq_acc.eq(tw_min) # 멈추면 주파수 초기화

        # --- LUT 로직 (이전과 동일) ---
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
        ]
        
        return m