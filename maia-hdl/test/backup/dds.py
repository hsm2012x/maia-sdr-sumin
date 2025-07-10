# dds.py 수정안

from amaranth import *
from amaranth.lib.wiring import Component, In, Out
from amaranth.lib.memory import Memory
import numpy as np

class DDS(Component):
    def __init__(self, *, tuning_word_0, tuning_word_1, tuning_word_2, hop_rate,
                 tuning_word_width=32, lut_addr_width=10, sample_width=12):
        
        # 파라미터를 Amaranth의 상수로 변환하여 저장
        self.tw0 = C(tuning_word_0, signed(tuning_word_width))
        self.tw1 = C(tuning_word_1, signed(tuning_word_width))
        self.tw2 = C(tuning_word_2, signed(tuning_word_width))
        self.hop_rate = C(hop_rate, range(hop_rate + 1))
        
        super().__init__({
            # 제어 입력 포트 제거, ready_in만 남김
            'ready_in': In(1),
            'dac_data_i': Out(signed(sample_width)),
            'dac_data_q': Out(signed(sample_width)),
        })
        self.tuning_word_width = tuning_word_width
        self.lut_addr_width = lut_addr_width
        self.sample_width = sample_width

    def elaborate(self, platform):
        m = Module()

        # --- 주파수 호핑 로직 ---
        # 3개의 주파수 튜닝 워드
        tw_neg_400k = C(-55924053, signed(self.tuning_word_width))
        tw_zero = C(0, signed(self.tuning_word_width))
        tw_pos_400k = C(55924053, signed(self.tuning_word_width))

        current_tuning_word = Signal.like(self.tw0)
        hop_counter = Signal.like(self.hop_rate)
        hop_state = Signal(2)

        # ready_in 신호가 활성화될 때만 카운터 동작
        with m.If(self.ready_in):
            with m.If(hop_counter >= self.hop_rate):
                m.d.sync += hop_counter.eq(0)
                m.d.sync += hop_state.eq(hop_state + 1)
            with m.Else():
                m.d.sync += hop_counter.eq(hop_counter + 1)

        # 상태에 따라 튜닝 워드 선택 (Mux)
        with m.Switch(hop_state):
            with m.Case(0):
                m.d.comb += current_tuning_word.eq(tw_neg_400k)
            with m.Case(1):
                m.d.comb += current_tuning_word.eq(tw_zero)
            with m.Case(2):
                m.d.comb += current_tuning_word.eq(tw_pos_400k)
            with m.Default():
                m.d.comb += current_tuning_word.eq(tw_zero)

        # --- 위상 누산기 및 LUT (기존과 유사) ---
        phase_acc = Signal(self.tuning_word_width)
        with m.If(self.ready_in):
            m.d.sync += phase_acc.eq(phase_acc + current_tuning_word)

        lut_size = 1 << self.lut_addr_width
        sin_table_init = [int(np.sin(2 * np.pi * i / lut_size) * ((1 << (self.sample_width - 1)) - 1)) for i in range(lut_size)]
        
        sin_lut = Memory(shape=signed(self.sample_width), depth=lut_size, init=sin_table_init)
        
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