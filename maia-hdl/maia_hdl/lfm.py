# test_lfm.py 파일 상단 LFM 클래스 정의 수정

from amaranth import *
from amaranth.lib.memory import Memory
import numpy as np

class LFM(Elaboratable):
    def __init__(self, tuning_word_width=32, lut_addr_width=10, sample_width=12):
        
        # --- LFM 파라미터 정의 ---
        self.tw_min = C(-349525333, signed(tuning_word_width)) # -2.5 MHz
        self.tw_max = C(349525333, signed(tuning_word_width))  # +2.5 MHz
        self.chirp_step = C(170666, signed(tuning_word_width))  # 주파수 증가량
        
        # --- 포트 정의 ---
        # super().__init__() 대신 self.포트이름 형태로 직접 선언합니다.
        self.ready_in = Signal()
        self.dac_data_i = Signal(signed(sample_width))
        self.dac_data_q = Signal(signed(sample_width))
        
        # 내부 변수
        self.tuning_word_width = tuning_word_width
        self.lut_addr_width = lut_addr_width
        self.sample_width = sample_width

    def ports(self):
        """VCD 파형 저장을 위해 포트 목록을 반환하는 메소드"""
        return [
            self.ready_in,
            self.dac_data_i,
            self.dac_data_q,
        ]

    def elaborate(self, platform):
        m = Module()

        # --- LFM(Chirp) 로직 ---
        freq_acc = Signal.like(self.tw_min, reset=-349525333)

        with m.If(self.ready_in):
            m.d.sync += freq_acc.eq(freq_acc + self.chirp_step)
            with m.If(freq_acc >= self.tw_max):
                m.d.sync += freq_acc.eq(self.tw_min)

        # --- 위상 누산기 및 LUT ---
        phase_acc = Signal(self.tuning_word_width)
        with m.If(self.ready_in):
            m.d.sync += phase_acc.eq(phase_acc + freq_acc)

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

#
# --- 이하 if __name__ == '__main__': 블록은 수정할 필요 없습니다 ---
#