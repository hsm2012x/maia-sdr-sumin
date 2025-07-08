# 필요한 모듈 추가

import argparse

from amaranth import *
from amaranth.lib.cdc import FFSynchronizer, PulseSynchronizer
import amaranth.back.verilog
from amaranth.lib.fifo import SyncFIFO

# ... (기존 import)

# 1. 루프백 로직을 별도의 Elaboratable 클래스로 분리
class LoopbackPath(Elaboratable):
    def __init__(self, iq_width=12):
        self.iq_width = iq_width

        # 입력 포트
        self.rx_re_in = Signal(iq_width)
        self.rx_im_in = Signal(iq_width)
        self.rx_strobe_in = Signal()
        self.tx_ready_in = Signal()
        self.loopback_enabled = Signal() # 제어 신호

        # 출력 포트
        self.tx_re_out = Signal(16)
        self.tx_im_out = Signal(16)

    def elaborate(self, platform):
        m = Module()

        # FIFO 생성 (이제 이 로직 전체가 'sampling' 도메인에서 동작)
        m.submodules.fifo = fifo = SyncFIFO(width=24, depth=16)

        # FIFO 쓰기
        m.d.comb += [
            fifo.w_en.eq(self.rx_strobe_in),
            fifo.w_data.eq(Cat(self.rx_re_in, self.rx_im_in))
        ]

        # FIFO 읽기 (핸드셰이크)
        m.d.comb += fifo.r_en.eq(self.loopback_enabled & self.tx_ready_in & fifo.r_rdy)

        # 데이터 포맷팅 및 출력
        shift = 16 - self.iq_width
        fifo_re_out = Signal(self.iq_width)
        fifo_im_out = Signal(self.iq_width)
        m.d.comb += [
            fifo_re_out.eq(fifo.r_data[:self.iq_width]),
            fifo_im_out.eq(fifo.r_data[self.iq_width:]),
        ]
        
        # FIFO 출력을 등록하여 파이프라이닝 효과 추가
        m.d.sync += [
            self.tx_re_out.eq(fifo_re_out << shift),
            self.tx_im_out.eq(fifo_im_out << shift)
        ]

        return m