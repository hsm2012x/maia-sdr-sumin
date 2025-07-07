# dds.py (최종 버전)

from amaranth import *
from amaranth.lib.wiring import Component, In, Out
from amaranth.lib.memory import Memory
import numpy as np

class DDS(Component):
    # __init__ 에서 clk, rst 포트 제거
    def __init__(self, tuning_word_width=32, lut_addr_width=10, sample_width=12):
        super().__init__({
            # AXI-Lite 포트는 향후 사용을 위해 남겨둡니다.
            'axi_addr': In(4), 'axi_wdata': In(32), 'axi_wstrb': In(4),
            'axi_rdata': Out(32), 'axi_rvalid': Out(1), 'axi_wready': Out(1),
            'axi_rready': In(1), 'axi_bvalid': Out(1), 'axi_bready': In(1),
            
            'dac_data_i': Out(signed(sample_width)),
            'dac_data_q': Out(signed(sample_width)),
            'dac_valid': Out(1)
        })
        self.tuning_word_width = tuning_word_width
        self.lut_addr_width = lut_addr_width
        self.sample_width = sample_width

    def elaborate(self, platform):
        m = Module()

        # 로컬 클럭 도메인 정의 로직을 완전히 삭제합니다.
        # 이 모듈의 'sync' 로직은 부모 모듈의 'sync' 도메인에 의해 구동됩니다.

        tuning_word = Signal(self.tuning_word_width, reset=int(0.05 * (1 << self.tuning_word_width)))
        
        m.d.comb += self.axi_wready.eq(1) 
        m.d.comb += self.axi_bvalid.eq(0) 

        phase_acc = Signal(self.tuning_word_width)
        m.d.sync += phase_acc.eq(phase_acc + tuning_word)

        lut_size = 1 << self.lut_addr_width
        sin_table_init = [int(np.sin(2 * np.pi * i / lut_size) * ((1 << (self.sample_width - 1)) - 1)) for i in range(lut_size)]
        
        sin_lut = Memory(shape=signed(self.sample_width), depth=lut_size, init=sin_table_init)
        
        sin_rdport = sin_lut.read_port(domain="sync")
        cos_rdport = sin_lut.read_port(domain="sync")
        
        lut_address = phase_acc[-self.lut_addr_width:]
        m.d.comb += sin_rdport.addr.eq(lut_address)
        m.d.comb += cos_rdport.addr.eq(lut_address + (lut_size // 4))

        i_out_reg = Signal(signed(self.sample_width))
        q_out_reg = Signal(signed(self.sample_width))
        valid_reg = Signal()
        
        m.d.sync += [
            i_out_reg.eq(cos_rdport.data),
            q_out_reg.eq(sin_rdport.data),
            valid_reg.eq(1)
        ]

        m.d.comb += [
            self.dac_data_i.eq(i_out_reg),
            self.dac_data_q.eq(q_out_reg),
            self.dac_valid.eq(valid_reg)
        ]
        
        return m