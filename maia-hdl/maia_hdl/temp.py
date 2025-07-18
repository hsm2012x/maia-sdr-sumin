# #
# # Copyright (C) 2022-2025 Daniel Estevez <daniel@destevez.net>
# #
# # This file is part of maia-sdr
# #
# # SPDX-License-Identifier: MIT
# #

# import argparse

# from amaranth import *
# from amaranth.lib.cdc import FFSynchronizer, PulseSynchronizer
# from amaranth.lib.fifo import AsyncFIFO  # <<< 1. AsyncFIFO 임포트 추가
# import amaranth.back.verilog


# from .axi4_lite import Axi4LiteRegisterBridge
# from .cdc import RegisterCDC, RxIQCDC
# from .clknx import ClkNxCommonEdge
# from .config import MaiaSDRConfig
# from . import configs
# from .ddc import DDC
# from .pulse import PulseStretcher
# from .pluto_platform import PlutoPlatform
# from .register import Access, Field, Registers, Register, RegisterMap
# from .recorder import Recorder16IQ, RecorderMode
# from .spectrometer import Spectrometer
# from .lfm import LFM
# # IP core version
# _version = '0.6.2'


# class MaiaSDR(Elaboratable):
#     """Maia SDR top level

#     This elaboratable is the top-level Maia SDR IP core.
#     """
#     def __init__(self, config=MaiaSDRConfig()):
#         config.validate()
#         self.config = config
#         self.axi4_awidth = 4
#         self.s_axi_lite = ClockDomain()
#         self.sampling = ClockDomain()
#         # A clock domain called 'sync' is added to override the default
#         # behaviour, since we drive the reset internally.
#         #
#         # See https://github.com/amaranth-lang/amaranth/issues/1506
#         self.sync = ClockDomain()
#         self.clk2x = ClockDomain()
#         self.clk3x = ClockDomain()
#         self.dac = ClockDomain()
#         self.axi4lite = Axi4LiteRegisterBridge(
#             self.axi4_awidth, name='s_axi_lite')
#         self.control_registers = Registers(
#             'control',
#             {
#                 0b00: Register(
#                     'product_id', [
#                         Field('product_id', Access.R, 32, 0x6169616d)
#                     ]),
#                 0b01: Register('version', [
#                     Field('bugfix', Access.R, 8,
#                           int(_version.split('.')[2])),
#                     Field('minor', Access.R, 8,
#                           int(_version.split('.')[1])),
#                     Field('major', Access.R, 8,
#                           int(_version.split('.')[0])),
#                     Field('platform', Access.R, 8, config.platform),
#                 ]),
#                 0b10: Register('control', [
#                     Field('sdr_reset', Access.RW, 1, 1),
#                 ]),
#                 0b11: Register('interrupts', [
#                     Field('spectrometer', Access.Rsticky, 1, 0),
#                     Field('recorder', Access.Rsticky, 1, 0),
#                 ], interrupt=True),
#             },
#             2)
#         self.recorder_registers = Registers(
#             'recorder',
#             {
#                 0b0: Register('recorder_control', [
#                     Field('start', Access.Wpulse, 1, 0),
#                     Field('stop', Access.Wpulse, 1, 0),
#                     Field('mode', Access.RW,
#                           Shape.cast(RecorderMode).width, 0),
#                     Field('dropped_samples', Access.R, 1, 0),
#                 ]),
#                 0b1: Register('recorder_next_address', [
#                     Field('next_address', Access.R, 32, 0),
#                 ]),
#             },
#             1)
#         self.spectrometer = Spectrometer(
#             config.spectrometer_address,
#             config.spectrometer_buffers.bit_length() - 1,
#             dma_name='m_axi_spectrometer')
#         self.recorder = Recorder16IQ(
#             config.recorder_address_range[0],
#             config.recorder_address_range[1],
#             dma_name='m_axi_recorder', domain_in='sync',
#             domain_dma='s_axi_lite')
#         self.ddc = DDC('clk3x')
#         self.sdr_registers = Registers(
#             'sdr', {
#                 0b000: Register(
#                     'spectrometer',
#                     [
#                         Field('use_ddc_out',
#                               Access.RW,
#                               1,
#                               0),
#                         Field('num_integrations',
#                               Access.RW,
#                               self.spectrometer.nint_width,
#                               -1),
#                         Field('abort', Access.Wpulse, 1, 0),
#                         Field('last_buffer',
#                               Access.R,
#                               len(self.spectrometer.last_buffer),
#                               0),
#                         Field('peak_detect',
#                               Access.RW,
#                               1,
#                               0),
#                     ]),
#                 0b001: Register(
#                     'ddc_coeff_addr',
#                     [
#                         Field('coeff_waddr',
#                               Access.RW,
#                               10,
#                               0),
#                     ]),
#                 0b010: Register(
#                     'ddc_coeff',
#                     [
#                         Field('coeff_wren',
#                               Access.Wpulse,
#                               1,
#                               0),
#                         Field('coeff_wdata',
#                               Access.RW,
#                               18,
#                               0),
#                     ]),
#                 0b011: Register(
#                     'ddc_decimation',
#                     [
#                         Field('decimation1',
#                               Access.RW,
#                               7,
#                               0),
#                         Field('decimation2',
#                               Access.RW,
#                               6,
#                               0),
#                         Field('decimation3',
#                               Access.RW,
#                               7,
#                               0),
#                     ]),
#                 0b100: Register(
#                     'ddc_frequency',
#                     [
#                         Field('frequency',
#                               Access.RW,
#                               28,
#                               0),
#                     ]),
#                 0b101: Register(
#                     'ddc_control',
#                     [
#                         Field('operations_minus_one1',
#                               Access.RW,
#                               7,
#                               0),
#                         Field('operations_minus_one2',
#                               Access.RW,
#                               6,
#                               0),
#                         Field('operations_minus_one3',
#                               Access.RW,
#                               7,
#                               0),
#                         Field('odd_operations1',
#                               Access.RW,
#                               1,
#                               0),
#                         Field('odd_operations3',
#                               Access.RW,
#                               1,
#                               0),
#                         Field('bypass2',
#                               Access.RW,
#                               1,
#                               0),
#                         Field('bypass3',
#                               Access.RW,
#                               1,
#                               0),
#                         Field('enable_input',
#                               Access.RW,
#                               1,
#                               0),
#                     ]),
#                     0b110:Register('tx_control', [
#                         Field('source_select', Access.RW, 2, 1) # 0=DDS, 1=LFM
#                     ]),
#             }, 4 )
#         self.lfm = LFM()

#         metadata = {
#             'vendor': 'Daniel Estevez',
#             'vendorID': 'destevez.net',
#             'name': 'Maia SDR',
#             'series': 'Maia SDR',
#             'version': _version,
#             'description': f'Maia SDR IP core (platform {config.platform})',
#             'licenseText': ('SPDX-License-Identifier: MIT '
#                             'Copyright (C) Daniel Estevez 2022-2024'),
#         }

#         self.lfm_registers = Registers(
#             'lfm', {
#                 0b00: Register('lfm_control', [
#                     Field('start', Access.Wpulse, 1, 0),
#                     Field('stop', Access.Wpulse, 1, 0),
#                     Field('running', Access.R, 1, 0),
#                 ]),
#                 0b01: Register('lfm_tw_min', [
#                     Field('value', Access.RW, 32, 0)
#                 ]),
#                 0b10: Register('lfm_tw_max', [
#                     Field('value', Access.RW, 32, 349525333)
#                 ]),
#                 0b11: Register('lfm_chirp_step', [
#                     Field('value', Access.RW, 32, 170666)
#                 ]),
#                 # ... 추가 레지스터 ...
#             }, 2) # 주소 비트 2개 (4개 레지스터)
#         self.register_map = RegisterMap({
#             0x0: self.control_registers,
#             0x10: self.recorder_registers,
#             0x20: self.sdr_registers,
#             0x40: self.lfm_registers
#         }, metadata)

#         self.iq_in_width = 12
#         self.re_in = Signal(self.iq_in_width)
#         self.im_in = Signal(self.iq_in_width)
#         self.interrupt_out = Signal()

#         self.dac_clk_in = Signal()
#         self.dac_enable_in = Signal()
#         self.dac_valid_in = Signal()
#         self.tx_re_out = Signal(12)
#         self.tx_im_out = Signal(12)

#     def ports(self):
#         return (
#             self.axi4lite.axi.ports()
#             + self.spectrometer.dma.axi.ports()
#             + self.recorder.dma.axi.ports()
#             + [
#                 self.re_in,
#                 self.im_in,
#                 self.interrupt_out,
#                 self.s_axi_lite.clk,
#                 self.s_axi_lite.rst,
#                 self.sampling.clk,
#                 self.sync.clk,
#                 self.sync.rst,
#                 self.clk2x.clk,
#                 self.clk3x.clk,
#                 self.dac_enable_in,
#                 self.dac_valid_in,
#                 self.tx_re_out,
#                 self.tx_im_out,
#                 self.dac_clk_in,

#             ]
#         )

#     def svd(self):
#         return self.register_map.svd()

#     def elaborate(self, platform):
#         m = Module()
#         m.domains += [
#             self.s_axi_lite,
#             self.sampling,
#             self.sync,
#             self.clk2x,
#             self.clk3x,
#             self.dac,
#         ]
#         m.d.comb += ClockSignal("dac").eq(self.dac_clk_in)
#         s_axi_lite_renamer = DomainRenamer({'sync': 's_axi_lite'})
#         m.submodules.axi4lite = s_axi_lite_renamer(self.axi4lite)
#         m.submodules.control_registers = s_axi_lite_renamer(
#             self.control_registers)
#         m.submodules.recorder_registers = s_axi_lite_renamer(
#             self.recorder_registers)
#         m.submodules.spectrometer = self.spectrometer
#         m.submodules.sync_spectrometer_interrupt = \
#             sync_spectrometer_interrupt = PulseSynchronizer(
#                 i_domain='sync', o_domain='s_axi_lite')
#         m.submodules.recorder = self.recorder
#         m.submodules.ddc = self.ddc
#         m.submodules.sdr_registers = self.sdr_registers
#         m.submodules.sdr_registers_cdc = sdr_registers_cdc = RegisterCDC(
#             's_axi_lite', 'sync', self.sdr_registers.aw)
#         m.submodules.common_edge_2x = common_edge_2x = ClkNxCommonEdge(
#             'sync', 'clk2x', 2)
#         m.submodules.common_edge_3x = common_edge_3x = ClkNxCommonEdge(
#             'sync', 'clk3x', 3)

#         # RX IQ CDC
#         m.submodules.rxiq_cdc = rxiq_cdc = RxIQCDC(
#             'sampling', 'sync', self.iq_in_width)
#         m.d.comb += [rxiq_cdc.re_in.eq(self.re_in),
#                      rxiq_cdc.im_in.eq(self.im_in)]

#         # Spectrometer (sync domain)
#         spectrometer_re_in = Signal(
#             self.spectrometer.width_in, reset_less=True)
#         spectrometer_im_in = Signal(
#             self.spectrometer.width_in, reset_less=True)
#         assert len(spectrometer_re_in) == len(self.ddc.re_out)
#         assert len(spectrometer_im_in) == len(self.ddc.im_out)
#         spectrometer_strobe_in = Signal()
#         with m.If(self.sdr_registers['spectrometer']['use_ddc_out']):
#             m.d.sync += [
#                 spectrometer_re_in.eq(self.ddc.re_out),
#                 spectrometer_im_in.eq(self.ddc.im_out),
#                 spectrometer_strobe_in.eq(self.ddc.strobe_out),
#             ]
#         with m.Else():
#             shift = self.spectrometer.width_in - self.iq_in_width
#             m.d.sync += [
#                 # The RX IQ samples have 12 bits, but the spectrometer input
#                 # has 16 bits. Push the 12 bits to the MSBs.
#                 spectrometer_re_in.eq(rxiq_cdc.re_out << shift),
#                 spectrometer_im_in.eq(rxiq_cdc.im_out << shift),
#                 spectrometer_strobe_in.eq(rxiq_cdc.strobe_out),
#             ]
#         # spectrometer reg
#         m.d.comb += [
#             self.spectrometer.strobe_in.eq(spectrometer_strobe_in),
#             self.spectrometer.common_edge_2x.eq(common_edge_2x.common_edge),
#             self.spectrometer.common_edge_3x.eq(common_edge_3x.common_edge),
#             self.spectrometer.re_in.eq(spectrometer_re_in),
#             self.spectrometer.im_in.eq(spectrometer_im_in),
#             sync_spectrometer_interrupt.i.eq(self.spectrometer.interrupt_out),
#             self.spectrometer.number_integrations.eq(
#                 self.sdr_registers['spectrometer']['num_integrations']),
#             self.spectrometer.abort.eq(
#                 self.sdr_registers['spectrometer']['abort']),
#             self.spectrometer.peak_detect.eq(
#                 self.sdr_registers['spectrometer']['peak_detect']),
#             self.sdr_registers['spectrometer']['last_buffer'].eq(
#                 self.spectrometer.last_buffer),
#         ]

#         # Recorder
#         m.d.comb += [
#             # sync domain
#             self.recorder.strobe_in.eq(spectrometer_strobe_in),
#             self.recorder.re_in.eq(spectrometer_re_in),
#             self.recorder.im_in.eq(spectrometer_im_in),
#             # s_axi_lite domain
#             self.recorder.mode.eq(
#                 self.recorder_registers['recorder_control']['mode']),
#             self.recorder.start.eq(
#                 self.recorder_registers['recorder_control']['start']),
#             self.recorder.stop.eq(
#                 self.recorder_registers['recorder_control']['stop']),
#             self.recorder_registers['recorder_control']['dropped_samples'].eq(
#                 self.recorder.dropped_samples),
#             (self.recorder_registers['recorder_next_address']
#              ['next_address'].eq(self.recorder.next_address)),
#         ]

#         # DDC
#         m.d.comb += [
#             self.ddc.common_edge.eq(common_edge_3x.common_edge),
#             self.ddc.enable_input.eq(
#                 self.sdr_registers['ddc_control']['enable_input']),
#             self.ddc.frequency.eq(
#                 self.sdr_registers['ddc_frequency']['frequency']),
#             self.ddc.coeff_waddr.eq(
#                 self.sdr_registers['ddc_coeff_addr']['coeff_waddr']),
#             self.ddc.coeff_wren.eq(
#                 self.sdr_registers['ddc_coeff']['coeff_wren']),
#             self.ddc.coeff_wdata.eq(
#                 self.sdr_registers['ddc_coeff']['coeff_wdata']),
#             self.ddc.decimation1.eq(
#                 self.sdr_registers['ddc_decimation']['decimation1']),
#             self.ddc.decimation2.eq(
#                 self.sdr_registers['ddc_decimation']['decimation2']),
#             self.ddc.decimation3.eq(
#                 self.sdr_registers['ddc_decimation']['decimation3']),
#             self.ddc.bypass2.eq(
#                 self.sdr_registers['ddc_control']['bypass2']),
#             self.ddc.bypass3.eq(
#                 self.sdr_registers['ddc_control']['bypass3']),
#             self.ddc.operations_minus_one1.eq(
#                 self.sdr_registers['ddc_control']['operations_minus_one1']),
#             self.ddc.operations_minus_one2.eq(
#                 self.sdr_registers['ddc_control']['operations_minus_one2']),
#             self.ddc.operations_minus_one3.eq(
#                 self.sdr_registers['ddc_control']['operations_minus_one3']),
#             self.ddc.odd_operations1.eq(
#                 self.sdr_registers['ddc_control']['odd_operations1']),
#             self.ddc.odd_operations3.eq(
#                 self.sdr_registers['ddc_control']['odd_operations3']),
#             self.ddc.strobe_in.eq(rxiq_cdc.strobe_out),
#             self.ddc.re_in.eq(rxiq_cdc.re_out),
#             self.ddc.im_in.eq(rxiq_cdc.im_out),
#         ]
        
#         # LFM
#         m.submodules.lfm = self.lfm

#         m.submodules.tx_fifo = tx_fifo = AsyncFIFO(
#             width=24, depth=16, r_domain="dac", w_domain="sync")


#         # Registers s_axi_lite domain
#         # TODO: convert all of this into a RegisterCrossbar module
#         address = Signal(self.axi4_awidth, reset_less=True)
#         wdata = Signal(32, reset_less=True)
#         sdr_regs_select = self.axi4lite.address[3] == 1
#         recorder_regs_select = (
#             ~sdr_regs_select & (self.axi4lite.address[2] == 1))
#         control_regs_select = (
#             ~sdr_regs_select & (self.axi4lite.address[2] == 0))
#         lfm_regs_select = self.axi4lite.address[4:7] == 0b100

#         m.d.s_axi_lite += [
#             self.axi4lite.rdata.eq(self.control_registers.rdata
#                                    | self.recorder_registers.rdata
#                                    | sdr_registers_cdc.i_rdata),
#             self.axi4lite.rdone.eq(self.control_registers.rdone
#                                    | self.recorder_registers.rdone
#                                    | sdr_registers_cdc.i_rdone),
#             self.axi4lite.wdone.eq(self.control_registers.wdone
#                                    | self.recorder_registers.wdone
#                                    | sdr_registers_cdc.i_wdone),
#             self.control_registers.ren.eq(
#                 self.axi4lite.ren & control_regs_select),
#             self.control_registers.wstrobe.eq(
#                 Mux(control_regs_select, self.axi4lite.wstrobe, 0)),
#             self.recorder_registers.ren.eq(
#                 self.axi4lite.ren & recorder_regs_select),
#             self.recorder_registers.wstrobe.eq(
#                 Mux(recorder_regs_select, self.axi4lite.wstrobe, 0)),
#             sdr_registers_cdc.i_ren.eq(
#                 self.axi4lite.ren & sdr_regs_select),
#             sdr_registers_cdc.i_wstrobe.eq(
#                 Mux(sdr_regs_select, self.axi4lite.wstrobe, 0)),
#             address.eq(self.axi4lite.address),
#             wdata.eq(self.axi4lite.wdata),
#             self.lfm_registers.ren.eq(self.lfm_registers.ren & lfm_regs_select),
#             self.lfm_registers.wstrobe.eq(
#                 Mux(lfm_regs_select, self.axi4lite.wstrobe, 0)
#             )
#         ]
#         # register block에 주소/데이터 전달
#         m.d.comb += [
#             self.control_registers.address.eq(address),
#             self.control_registers.wdata.eq(wdata),
#             self.recorder_registers.address.eq(address),
#             self.recorder_registers.wdata.eq(wdata),
#             sdr_registers_cdc.i_address.eq(address),
#             sdr_registers_cdc.i_wdata.eq(wdata),
#             self.lfm_registers.address.eq(address),
#             self.lfm_registers.wdata.eq(wdata),

#         ]

#         # Registers sync domain
#         m.d.comb += [
#             self.sdr_registers.ren.eq(sdr_registers_cdc.o_ren),
#             self.sdr_registers.wstrobe.eq(sdr_registers_cdc.o_wstrobe),
#             self.sdr_registers.address.eq(sdr_registers_cdc.o_address),
#             self.sdr_registers.wdata.eq(sdr_registers_cdc.o_wdata),
#             sdr_registers_cdc.o_rdone.eq(self.sdr_registers.rdone),
#             sdr_registers_cdc.o_wdone.eq(self.sdr_registers.wdone),
#             sdr_registers_cdc.o_rdata.eq(self.sdr_registers.rdata),
            
#         ]
#         # internal resets
#         # We use FFSynchronizer rather than ResetSynchronizer because of
#         # https://github.com/amaranth-lang/amaranth/issues/721
#         for internal in ['sync', 'clk2x', 'clk3x', 'sampling']:
#             setattr(m.submodules, f'{internal}_rst', FFSynchronizer(
#                 self.control_registers['control']['sdr_reset'],
#                 ResetSignal(internal), o_domain=internal,
#                 init=1))
#         m.d.comb += rxiq_cdc.reset.eq(
#             self.control_registers['control']['sdr_reset'])

#         # Interrupts (s_axi_lite domain)
#         interrupts_reg = self.control_registers['interrupts']
#         m.d.comb += [
#             self.interrupt_out.eq(interrupts_reg.interrupt),
#             interrupts_reg['spectrometer'].eq(sync_spectrometer_interrupt.o),
#             interrupts_reg['recorder'].eq(self.recorder.finished),
#         ]
#         # --- LFM 모듈과 레지스터 블록 연결 ---
#         m.d.comb += [
#             self.lfm.reg_addr.eq(self.lfm_registers.address),
#             self.lfm.reg_wdata.eq(self.lfm_registers.wdata),
#             # Wpulse는 1클럭 펄스이므로, wstrobe를 그대로 연결
#             self.lfm.reg_wstrobe.eq(self.lfm_registers.wstrobe.any()),
#             self.lfm_registers.rdata.eq(self.lfm.reg_rdata),
#         ]

#         lfm_is_running = self.lfm_registers['lfm_control']['running']
#         m.d.comb += [
#             self.lfm.dac_enable_in.eq(lfm_is_running),
#             self.lfm.dac_valid_in.eq(tx_fifo.w_rdy)
#         ]
#          # LFM의 출력을 FIFO의 쓰기 포트로 연결 (sync 도메인)
#         m.d.comb += tx_fifo.w_data.eq(Cat(self.lfm.dac_data_i, self.lfm.dac_data_q))
#         m.d.comb += tx_fifo.w_en.eq(lfm_is_running & tx_fifo.w_rdy)

#         # FIFO의 읽기 활성화 신호는 dac_clk 도메인의 신호들로 제어됩니다.
#         m.d.comb += tx_fifo.r_en.eq(self.dac_enable_in & self.dac_valid_in)
        
#         # FIFO의 읽기 데이터(dac 도메인)를 최종 출력 포트로 연결합니다.
#         m.d.comb += [
#             self.tx_re_out.eq(tx_fifo.r_data[0:12]),
#             self.tx_im_out.eq(tx_fifo.r_data[12:24]),
#         ]

#         return m


# def write_svd(path):
#     top = MaiaSDR()
#     with open(path, 'wb') as f:
#         f.write(top.svd())


# def parse_args():
#     parser = argparse.ArgumentParser()
#     parser.add_argument(
#         '--config', default='default',
#         help='Maia SDR configuration name [default=%(default)r]')
#     parser.add_argument(
#         'output_file', help='Output verilog file')
#     return parser.parse_args()


# def main():
#     args = parse_args()
#     config = getattr(configs, args.config)()
#     top = MaiaSDR(config)
#     platform = PlutoPlatform()
#     with open(args.output_file, 'w') as f:
#         f.write(amaranth.back.verilog.convert(
#             top, platform=platform, ports=top.ports()))


# if __name__ == '__main__':
#     main()

#     # lfm.py 파일 수정

# from amaranth import *
# from amaranth.lib.memory import Memory
# import numpy as np

# class LFM(Elaboratable):
#     def __init__(self, tuning_word_width=32, lut_addr_width=10, sample_width=12):
#         # --- 제어/상태 레지스터 포트 ---
#         # 이 포트들은 나중에 MaiaSDR 모듈 내부의 레지스터 블록에 연결됩니다.
#         self.reg_addr = Signal(4)
#         self.reg_wdata = Signal(32)
#         self.reg_wstrobe = Signal() # 쓰기 활성화
#         self.reg_rdata = Signal(32)
        
#         # --- 데이터 경로 포트 ---
#         self.dac_enable_in = Signal()
#         self.dac_valid_in = Signal()
#         self.dac_data_i = Signal(signed(sample_width))
#         self.dac_data_q = Signal(signed(sample_width))

#         # 내부 변수들...
#         self.tuning_word_width = tuning_word_width
#         self.lut_addr_width = lut_addr_width
#         self.sample_width = sample_width

#     def elaborate(self, platform):
#         m = Module()

#         # --- 제어 및 상태 레지스터용 내부 신호 ---
#         is_running = Signal(reset=0)
#         tw_min = Signal.like(C(0, signed(self.tuning_word_width)))
#         tw_max = Signal.like(C(0, signed(self.tuning_word_width)))
#         chirp_step = Signal.like(C(0, signed(self.tuning_word_width)))
#         valid_counter = Signal(32)

#         # --- AXI-Lite 쓰기 동작 처리 ---
#         with m.If(self.reg_wstrobe):
#             with m.Switch(self.reg_addr):
#                 with m.Case(0x00): # 제어 레지스터
#                     with m.If(self.reg_wdata[0]): # Start
#                         m.d.sync += is_running.eq(1)
#                     with m.If(self.reg_wdata[1]): # Stop
#                         m.d.sync += is_running.eq(0)
#                 with m.Case(0x04): # TW_MIN
#                     m.d.sync += tw_min.eq(self.reg_wdata)
#                 with m.Case(0x08): # TW_MAX
#                     m.d.sync += tw_max.eq(self.reg_wdata)
#                 with m.Case(0x0C): # CHIRP_STEP
#                     m.d.sync += chirp_step.eq(self.reg_wdata)

#         # --- AXI-Lite 읽기 동작 처리 ---
#         with m.Switch(self.reg_addr):
#             with m.Case(0x00): # 상태 레지스터
#                 m.d.comb += self.reg_rdata.eq(is_running)
#             with m.Case(0x04): # TW_MIN
#                 m.d.comb += self.reg_rdata.eq(tw_min)
#             # ... TW_MAX, CHIRP_STEP 읽기 로직 추가 가능 ...
#             with m.Case(0x10): # Valid 카운터
#                 m.d.comb += self.reg_rdata.eq(valid_counter)
#             with m.Default():
#                 m.d.comb += self.reg_rdata.eq(0)

#         # --- LFM/위상 누산기 로직 ---
#         freq_acc = Signal(signed(self.tuning_word_width), reset=0)
#         phase_acc = Signal(self.tuning_word_width)

#         with m.If(is_running & self.dac_enable_in & self.dac_valid_in):
#             m.d.sync += freq_acc.eq(freq_acc + chirp_step)
#             with m.If(freq_acc >= tw_max):
#                 m.d.sync += freq_acc.eq(tw_min)
            
#             m.d.sync += phase_acc.eq(phase_acc + freq_acc)
#             m.d.sync += valid_counter.eq(valid_counter + 1)
        
#         with m.If(~is_running):
#             m.d.sync += freq_acc.eq(tw_min) # 멈추면 주파수 초기화

#         # --- LUT 로직 (이전과 동일) ---
#         lut_size = 1 << self.lut_addr_width
#         sin_table_init = [int(np.sin(2 * np.pi * i / lut_size) * ((1 << (self.sample_width - 1)) - 1)) for i in range(lut_size)]
#         sin_lut = Memory(shape=signed(self.sample_width), depth=lut_size, init=sin_table_init)
#         m.submodules.sin_lut = sin_lut
#         sin_rdport = sin_lut.read_port(domain="sync")
#         cos_rdport = sin_lut.read_port(domain="sync")
#         lut_address = phase_acc[-self.lut_addr_width:]
#         m.d.comb += [
#             sin_rdport.addr.eq(lut_address),
#             cos_rdport.addr.eq(lut_address + (lut_size // 4)),
#             self.dac_data_i.eq(cos_rdport.data),
#             self.dac_data_q.eq(sin_rdport.data),
#         ]
        
#         return m