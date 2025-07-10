# dds.py (논리 충돌 및 버그 수정 최종 버전)

from amaranth import *
from amaranth.lib.wiring import Component, In, Out
from amaranth.lib.memory import Memory
import numpy as np

# 클래스 이름을 역할에 맞게 HoppingDDS로 변경하는 것을 추천합니다.
class DDS(Component):
    def __init__(self, *, tuning_word_0, tuning_word_1, tuning_word_2, hop_rate,
                 tuning_word_width=32, lut_addr_width=10, sample_width=12):
        
        # __init__에서 받은 파라미터를 Amaranth의 상수로 변환하여 저장
        self.tw0 = C(tuning_word_0, signed(tuning_word_width))
        self.tw1 = C(tuning_word_1, signed(tuning_word_width))
        self.tw2 = C(tuning_word_2, signed(tuning_word_width))
        self.hop_rate = C(hop_rate, range(hop_rate + 1))
        
        # Component를 상속받았으므로, 포트 정의는 super().__init__에서 처리
        super().__init__({
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
        # <<< 수정: 하드코딩된 튜닝 워드 삭제 >>>
        # current_tuning_word의 타입은 self.tw0에서 유추하므로 그대로 둠
        current_tuning_word = Signal.like(self.tw0)
        hop_counter = Signal.like(self.hop_rate)
        hop_state = Signal(2)

        with m.If(self.ready_in):
            with m.If(hop_counter >= self.hop_rate):
                m.d.sync += hop_counter.eq(0)
                m.d.sync += hop_state.eq(hop_state + 1)
            with m.Else():
                m.d.sync += hop_counter.eq(hop_counter + 1)

        # <<< 수정: 상태에 따라 __init__에서 전달받은 튜닝 워드(self.tw*)를 사용 >>>
        with m.Switch(hop_state):
            with m.Case(0):
                m.d.comb += current_tuning_word.eq(self.tw0)
            with m.Case(1):
                m.d.comb += current_tuning_word.eq(self.tw1)
            with m.Case(2):
                m.d.comb += current_tuning_word.eq(self.tw2)
            with m.Default():
                # 상태가 3이 되면 다시 첫 번째 주파수로 돌아감
                m.d.comb += current_tuning_word.eq(self.tw0)

        # --- 위상 누산기 및 LUT ---
        phase_acc = Signal(self.tuning_word_width)
        with m.If(self.ready_in):
            m.d.sync += phase_acc.eq(phase_acc + current_tuning_word)

        lut_size = 1 << self.lut_addr_width
        sin_table_init = [int(np.sin(2 * np.pi * i / lut_size) * ((1 << (self.sample_width - 1)) - 1)) for i in range(lut_size)]
        
        sin_lut = Memory(shape=signed(self.sample_width), depth=lut_size, init=sin_table_init)
        # <<< 수정: Memory를 서브모듈로 추가하여 UnusedElaboratable 버그 해결 >>>
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