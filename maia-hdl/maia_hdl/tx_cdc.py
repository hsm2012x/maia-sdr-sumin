# tx_cdc.py 최종 수정안

from amaranth import *
from .fifo import AsyncFifo18_36
import amaranth.back.verilog
from amaranth.lib.cdc import FFSynchronizer, PulseSynchronizer
class TxIQCDC(Elaboratable):
    """
    TX IQ 데이터 전송을 위한 CDC 모듈.
    LFM('sync' 도메인)에서 DAC('dac'/'sampling' 도메인)로 데이터를 전달
    """
    def __init__(self, i_domain: str, o_domain: str, width: int = 12):
        self._i_domain = i_domain # sync
        self._o_domain = o_domain # sampling
        self.w = width

        # --- 쓰기 측 포트 (LFM이 사용) ---
        self.re_in = Signal(signed(width))
        self.im_in = Signal(signed(width))
        self.w_en = Signal()      # LFM이 "데이터가 유효하다"고 알리는 신호
        self.w_rdy = Signal()     # FIFO가 "데이터를 받을 준비가 됐다"고 알리는 신호

        # --- 읽기 측 포트 (axi_ad9361이 사용) ---
        self.re_out = Signal(signed(width))
        self.im_out = Signal(signed(width))
        self.r_en = Signal()      # axi_ad9361이 "데이터를 달라"고 요청하는 신호
        
        # 외부에서 비동기 리셋을 받을 단일 포트
        self.reset_in = Signal()
       
        self.almost_empty = Signal() # FIFO가 거의 비었음을 알리는 플래그

    def elaborate(self, platform):
        m = Module()
        m.submodules.fifo = fifo = AsyncFifo18_36(
            r_domain=self._o_domain, w_domain=self._i_domain)

        reset_w = Signal()
        m.submodules.sync_reset_w = FFSynchronizer(
            self.reset_in, reset_w, o_domain=self._i_domain, init=1)

        # 2. 읽기(o_domain)측을 위한 동기화된 리셋 생성
        reset_r = Signal()
        m.submodules.sync_reset_r = FFSynchronizer(
            self.reset_in, reset_r, o_domain=self._o_domain, init=1)


        # --- 쓰기 측 ('sync' 도메인) ---
        m.d.comb += [
            fifo.data_in.eq(Cat(self.re_in, self.im_in)),
            fifo.wren.eq(self.w_en & self.w_rdy & ~reset_w),
            self.w_rdy.eq(~fifo.full),
        ]
        
        # --- 읽기 측 ('dac'/'sampling' 도메인) ---
        m.d.comb += [
            self.re_out.eq(fifo.data_out[:self.w]),
            self.im_out.eq(fifo.data_out[self.w:]),
            fifo.rden.eq(self.r_en & ~fifo.empty & ~reset_r),
            self.almost_empty.eq(fifo.empty)
        ]
        m.d.comb += fifo.reset.eq(self.reset_in)
        #m.d.comb += fifo.reset.eq(self.sdr_reset_sync)
        #m.d.comb += fifo.reset.eq(self.reset_in)
        return m