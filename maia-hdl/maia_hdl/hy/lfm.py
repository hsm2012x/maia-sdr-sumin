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

        # --- 제어 입력 포트 ---
        self.start_continuous_in = Signal()
        self.stop_continuous_in = Signal()
        self.start_1sec_pulse_in = Signal()

        # --- 설정 입력 포트 ---
        self.tw_min_in = Signal(signed(tuning_word_width))
        self.tw_max_in = Signal(signed(tuning_word_width))
        self.chirp_step_in = Signal(signed(tuning_word_width))
        # --- 모트 선택 및 기ㅏ본 CW 주파수 설정 입력 포트 추가 ---

        self.mode_in = Signal(2)

        # --- 상태 출력 포트 ---
        self.is_running_out = Signal()
        
        # --- 데이터 경로 포트 (표준 스트리밍 핸드셰이크) ---
        self.valid_out = Signal()
        self.ready_in = Signal()
        self.dac_data_i = Signal(signed(sample_width))
        self.dac_data_q = Signal(signed(sample_width))

    def elaborate(self, platform):
        m = Module()

        
        # --- 내부 상태 신호 ---
        continuous_running = Signal()
        timer_active = Signal()
        # --- 쓰기 로직 ---
        # 제어 명령을 위한 1클럭 펄스 생성
        PULSE_DURATION_CYCLES = self.CLK_FREQ
        timer_counter = Signal(range(PULSE_DURATION_CYCLES))
        with m.If(self.start_1sec_pulse_in):
            m.d.sync += timer_active.eq(1)
            m.d.sync += timer_counter.eq(0)
        with m.Elif(timer_active):
            with m.If(timer_counter == PULSE_DURATION_CYCLES - 1):
                m.d.sync += timer_active.eq(0)
            with m.Else():
                m.d.sync += timer_counter.eq(timer_counter + 1)

      
        with m.If(self.start_continuous_in):
            m.d.sync += continuous_running.eq(1)
        with m.If(self.stop_continuous_in):
            m.d.sync += continuous_running.eq(0)

         # 최종 실행 상태를 is_running_out 포트로 출력
        m.d.comb += self.is_running_out.eq(continuous_running | timer_active)
        m.d.comb += self.valid_out.eq(self.is_running_out)


        #=================================================================
        # 3. LFM 제어 상태 머신 (FSM)
        #=================================================================

        # --- 1초 펄스 타이머 로직 (버그 수정) ---
        PULSE_DURATION_CYCLES = self.CLK_FREQ
        timer_counter = Signal(range(PULSE_DURATION_CYCLES))

        with m.If(self.start_1sec_pulse_in):
            m.d.sync += timer_active.eq(1)
            m.d.sync += timer_counter.eq(0)
        with m.Elif(timer_active):
            with m.If(timer_counter == PULSE_DURATION_CYCLES - 1):
                m.d.sync += timer_active.eq(0)
            with m.Else():
                m.d.sync += timer_counter.eq(timer_counter + 1)
        
        # --- 연속/펄스 모드 통합 ---
        with m.If(self.start_continuous_in):
            m.d.sync += continuous_running.eq(1)
        with m.If(self.stop_continuous_in):
            m.d.sync += continuous_running.eq(0)

        m.d.comb += self.is_running_out.eq(continuous_running | timer_active)

          #=================================================================
        # 2. LFM 파형 생성 및 데이터 경로
        #=================================================================
        
       
        # --- 데이터 출력 핸드셰이크 ---
        # LFM이 실행 중일 때만 데이터가 유효하다고 외부에 알림
        m.d.comb += self.valid_out.eq(self.is_running_out)
        
        # --- 사인파형 Lut(Look-Up table) 정의 ---
        lut_size = 1 << self.LUT_ADDR_WIDTH
        sin_table_init = [int(np.sin(2 * np.pi * i / lut_size) * ((1 << (self.SAMPLE_WIDTH - 1)) - 1)) for i in range(lut_size)]
        m.submodules.sin_lut = sin_lut = Memory(shape=signed(self.SAMPLE_WIDTH), depth=lut_size, init=sin_table_init)

        
        freq_acc = Signal.like(self.tw_min_in)
        phase_acc = Signal.like(self.tw_min_in)

        with m.Switch(self.mode_in):

            with m.Case(1):
                # --- LFM 모드에서 사용할 Lut 읽기 포트 
                sin_rdport = sin_lut.read_port(domain="sync")
                cos_rdport = sin_lut.read_port(domain="sync")
                with m.If(self.valid_out & self.ready_in):
                    m.d.sync += freq_acc.eq(freq_acc + self.chirp_step_in)
                    with m.If(freq_acc >= self.tw_max_in):
                        m.d.sync += freq_acc.eq(self.tw_min_in)
                    m.d.sync += phase_acc.eq(phase_acc + freq_acc)
                
                # BUG 4 FIX: 위상 누적기도 함께 리셋하여 시작 시점의 위상 불일치 방지
                with m.If(~self.is_running_out):
                    m.d.sync += freq_acc.eq(self.tw_min_in)
                    m.d.sync += phase_acc.eq(0)

                lut_address = phase_acc[-self.LUT_ADDR_WIDTH:]
                m.d.comb += [
                    sin_rdport.addr.eq(lut_address),
                    cos_rdport.addr.eq(lut_address + (lut_size // 4)),
                    self.dac_data_i.eq(cos_rdport.data),
                    self.dac_data_q.eq(sin_rdport.data),
                ]

            with m.Case(2):
                sin_rdport1 = sin_lut.read_port(domain="sync")
                cos_rdport1 = sin_lut.read_port(domain="sync")
                sin_rdport2 = sin_lut.read_port(domain="sync")
                cos_rdport2 = sin_lut.read_port(domain="sync")

                # CW 모드를 위한 위상 누적기 (freq_acc와 별도)
                phase_acc_cw1 = Signal.like(self.tw_min_in)
                phase_acc_cw2 = Signal.like(self.tw_min_in)

                with m.If(self.valid_out & self.ready_in):
                    # BUG 1 FIX: 의도대로 tw_min/max_in을 CW 주파수 튜닝 워드로 사용
                    m.d.sync += phase_acc_cw1.eq(phase_acc_cw1 + self.tw_min_in)
                    m.d.sync += phase_acc_cw2.eq(phase_acc_cw2 + self.tw_max_in)

                lut_addr_cw1 = phase_acc_cw1[-self.LUT_ADDR_WIDTH:]
                lut_addr_cw2 = phase_acc_cw2[-self.LUT_ADDR_WIDTH:]
                m.d.comb += [
                    sin_rdport1.addr.eq(lut_addr_cw1),
                    cos_rdport1.addr.eq(lut_addr_cw1 + (lut_size // 4)),
                    sin_rdport2.addr.eq(lut_addr_cw2),
                    cos_rdport2.addr.eq(lut_addr_cw2 + (lut_size // 4)),
                ]

                sum_i = Signal(signed(self.SAMPLE_WIDTH + 1))
                sum_q = Signal(signed(self.SAMPLE_WIDTH + 1))
                m.d.comb += [
                    sum_i.eq(cos_rdport1.data + cos_rdport2.data),
                    sum_q.eq(sin_rdport1.data + sin_rdport2.data),
                ]

                max_val = (1 << (self.SAMPLE_WIDTH - 1)) - 1
                min_val = -(1 << (self.SAMPLE_WIDTH - 1))
                with m.If(sum_i > max_val):
                    m.d.comb += self.dac_data_i.eq(max_val)
                with m.Elif(sum_i < min_val):
                    m.d.comb += self.dac_data_i.eq(min_val)
                with m.Else():
                    m.d.comb += self.dac_data_i.eq(sum_i)

                with m.If(sum_q > max_val):
                    m.d.comb += self.dac_data_q.eq(max_val)
                with m.Elif(sum_q < min_val):
                    m.d.comb += self.dac_data_q.eq(min_val)
                with m.Else():
                    m.d.comb += self.dac_data_q.eq(sum_q)
            
            # BUG 3 FIX: Default 문을 Switch문의 올바른 위치로 이동
            with m.Default():
                m.d.comb += [
                    self.dac_data_i.eq(0),
                    self.dac_data_q.eq(0),
                ]

        return m