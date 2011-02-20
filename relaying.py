# #!/usr/bin/env python

# Copyright (C) 2010  Sebastian Bittl
# This file is part of Relaying Schemes Implementation.

# Relaying Schemes Implementation is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# Relaying Schemes Implementation is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with Foobar.  If not, see <http://www.gnu.org/licenses/>.

from reedsolomon import Codec
from gnuradio import gr, gru, modulation_utils
from gnuradio import usrp
from gnuradio import eng_notation
from gnuradio.eng_option import eng_option
from optparse import OptionParser

import random, time, sys
from struct import pack, unpack

from subprocess import Popen

import os, signal
from numpy import frombuffer,bitwise_xor,byte, zeros, int8
import socket

# from current dir
import usrp_transmit_path
import usrp_receive_path

global verbose, test, measurement
verbose = False # enables debug output
measurement = False # stops the relay after 20000 transmissions

# path for transmitting data

class mytx_top_block(gr.top_block):
    def __init__(self, modulator, options):
        gr.top_block.__init__(self)

        self.txpath = usrp_transmit_path.usrp_transmit_path(modulator, options)

        self.connect(self.txpath)

# path for receiving data

class myrx_top_block(gr.top_block):
    def __init__(self, demodulator, rx_callback, options):
        gr.top_block.__init__(self)

        # Set up receive path
        self.rxpath = usrp_receive_path.usrp_receive_path(demodulator, rx_callback, options) 

        self.connect(self.rxpath)

# class for holding the fixed set of parameters taken from benchmark_rx/tx

class parameter:
    SIDE = 'B'
    FREQUENCY =  '5375M' #'2490M'
    RATE = '512k'
    TX_GAIN = '20'
    RX_GAIN = '66'
    MODULATION = 'gmsk' # possible are: cpm, d8psk, dbpsk,dqpsk, gmsk
    
    def __init__(self, side, freq, rate, tx_gain, rx_gain):
        if side is not None:
            self.SIDE = str(side)
            self.FREQUENCY = str(freq)
            self.RATE = str(rate)
            self.TX_GAIN = str(tx_gain)
            self.RX_GAIN = str(rx_gain)
        
    # this function sets the transmission parameters
    def set_tx_parameters(self):
        # declare parser for determining the options of transmitter
        parser_tx = OptionParser(option_class=eng_option, conflict_handler="resolve")
        expert_tx_grp = parser_tx.add_option_group("Expert")
        mods = modulation_utils.type_1_mods()       # all types of modulation
        # enable getting type of modulation
        parser_tx.add_option("-m", "--modulation", type="choice", choices=mods.keys(),
                      default='gmsk', help="Select modulation from: %s [default=%%default]" % (', '.join(mods.keys()),))
        # get packet size
        parser_tx.add_option("-s", "--size", type="eng_float", default=1500, help="set packet size [default=%default]")
        # get amount of random data to transfer
        parser_tx.add_option("-M", "--megabytes", type="eng_float", default=1.0, help="set megabytes to transmit [default=%default]")
        # determine wheater transferred data should be read from a file
        parser_tx.add_option("","--from-file", default=None, help="use file for packet contents")
        usrp_transmit_path.add_options(parser_tx, expert_tx_grp)

        for mod in mods.values():
            mod.add_options(expert_tx_grp)

        # argument list for configuring the transmitter
        temp = sys.argv[0]
        sys.argv = [temp,'','','','','','','']
        sys.argv[1] = '-T' + self.SIDE
        sys.argv[2] = '-f' + self.FREQUENCY
        sys.argv[3] = '-v'
        sys.argv[4] = '--tx-gain=' + self.TX_GAIN
        sys.argv[5] = '-r' + self.RATE
        sys.argv[6] = '-m' + self.MODULATION

        (options_tx, args_tx) = parser_tx.parse_args ()

        if options_tx.tx_freq is None:
            sys.stderr.write("You must specify -f FREQ or --freq FREQ\n")
            parser_tx.print_help(sys.stderr)
            sys.exit(1)

        if options_tx.from_file is not None:
            source_file = open(options_tx.from_file, 'r')
        return options_tx
    #--------------------------------------------------

    # this function sets the receiver parameters
    def set_rx_parameters(self):
        # declare parser for determining the options ofreceiver
        parser_rx = OptionParser(option_class=eng_option, conflict_handler="resolve")
        expert_rx_grp = parser_rx.add_option_group("Expert")
        demods = modulation_utils.type_1_demods()   # all types of demodulation
        # get type of demodulation
        parser_rx.add_option("-m", "--modulation", type="choice", choices=demods.keys(), 
                      default='gmsk', help="Select modulation from: %s [default=%%default]" % (', '.join(demods.keys()),))
        usrp_receive_path.add_options(parser_rx, expert_rx_grp)
     
        for mod in demods.values():
            mod.add_options(expert_rx_grp)

        # argument list for configuring the receiver
        sys.argv[1] = '-R' + self.SIDE
        sys.argv[2] = '-f' + self.FREQUENCY
        sys.argv[3] = '-v'
        sys.argv[4] = '--rx-gain=' + self.RX_GAIN
        sys.argv[5] = '-r' + self.RATE
        sys.argv[6] = '-m' + self.MODULATION
        
        (options_rx, args_rx) = parser_rx.parse_args ()

        if options_rx.rx_freq is None:
            sys.stderr.write("You must specify -f FREQ or --freq FREQ\n")
            parser_rx.print_help(sys.stderr)
            sys.exit(1)
        return options_rx
    #--------------------------------------------------
# end of class parameter

#class for holding the information about the header and for generating a header

class protocol_header:
    RQA = 0x01      # A is requested to send data
    RQB = 0x02      # B is requested to send data
    R_BIT = 0x04    # packet was sent by relay
    QA = 0x08       #source of packet is A
    QB = 0x10       #source of packet is B
    NC = 0x20       # packet included network coded data
    LIB = 0x40      # last in burst bit, station will not send data immediatly after this packet
    RESERVED = 0x80 # reserved bit
    REQUEST_ADRESS_A = 0
    REQUEST_ADRESS_B = 32768
    
    packet_id = 0
    MY_REQUEST = 0x00   # default value ensures that for a relay there cannot be a request
    
    def __init__(self, node_id = None):   # node id is only neccessary if we have a node
        if node_id is not None:
            if node_id == 'A':
                self.MY_REQUEST = self.RQA
            elif node_id == 'B':
                self.MY_REQUEST = self.RQB
            else:
                print "Error: No request bit is defined for this ID!"
        else:
            pass    # no node-id -> relay and nothing has to be done
    
    # for checking if the current packet is the last one in a packet burst
    def check_for_burst_end(self, header_first):
        if (header_first & self.LIB) != 0:
            return True
        else:
            return False
    
    # a function used to analyse the content of the first byte of the header of a packet
    # returns a tuple of true/false values indicating the the values of the corresponding bits in the first header byte
    # format of tuple: R-Bit, NC-Bit, Request of this station - Bit, Last In Burst - Bit, Source of packet is A - Bit, Source of packet is B - Bit
    def analyse_header(self, header_first):
        if (header_first & self.R_BIT) != 0:
            r_bit = True
        else:
            r_bit = False
        if (header_first & self.NC) != 0:
            nc = True
        else:
            nc = False
        if (header_first & self.MY_REQUEST) != 0:
            request = True
        else:
            request = False
        if (header_first & self.LIB) != 0:
            last_in_burst = True
        else:
            last_in_burst = False
        if (header_first & self.QA) != 0:
            source_is_A = True
        else:
            source_is_A = False
        if (header_first & self.QB) != 0:
            source_is_B = True
        else:
            source_is_B = False
        return (r_bit, nc, request, last_in_burst, source_is_A,  source_is_B)
    
    # this function creates the header of the relay- packet
    # the arguments are as follows:
    # length: a string representing the length of the packet coded with pack('!B', "the length")
    # req_a:  should a data request be made to A?
    # req_b:  should a data request be mode to B?
    # packet_id_a: 1. the ID of the packet when it is not network-coded, 2. the ID of the packet formerly sent from A, which is now part of the network-coded packet
    # packet_id_b: the ID of the packet formerly sent from B , which is now part of the network-coded packet
    # nc:     is the packet network-coded? this also means that all source bits are set
    # source: this parameter is only necessary if nc == False in order to indicate the source of the packet, valid values are 'A' and 'B'
    def create_header_relay(self, length = '', req_a = False, req_b = False, packet_id_a = '', packet_id_b = '', nc = False, source = None):
        header = ['', '', '', '', '', '']
        # check for errors first
        if (req_a == True) and (req_b == True):      #this should not occure!
            print "Error: only a single request is allowed!"
            sys.exit(1)
        if ((nc == True) and (packet_id_a == '')) or ((nc == True) and (packet_id_b == '')):
            print "Error: networkcoding is only allowed for two specified packets with a packet ID!"
            sys.exit(1)

        if req_a == True:   #request to A
            header[0] = 0 | self.RQA | self.R_BIT
            header[1:3] = pack('!H', self.REQUEST_ADRESS_A)
        elif req_b == True: #request to B
            header[0] = 0 | self.RQB | self.R_BIT
            header[1:3] = pack('!H', self.REQUEST_ADRESS_B)
        else:
            header[0] = 0 | self.R_BIT

        if (packet_id_a == '') and (packet_id_b == ''):
            header[3] = length    # pure request => length is 0
        else:   # data packet
            header[1] = packet_id_a[0]
            header[2] = packet_id_a[1]
            if nc == True:          # networkcoded packet
                header[0] |= self.NC   # set NC-bit
                # a network coded packet contains always data from both nodes
                header[0] |= self.QA | self.QB
                
                header[3] = packet_id_b[0]
                header[4] = packet_id_b[1]
                header[5] = length
            else:
                header[3] = length
                if source == 'A':
                    header[0] |= self.QA
                elif source == 'B':
                    header[0] |= self.QB
                else:
                    print "Error: data has no source!"
        header[0] = pack('!B', int(header[0]))
        slist = [str(elt) for elt in header] # does (str(header[0]) + str(header[1]) + str(header[2]) + str(header[3]) + str(header[4]) + str(header[5])) more performant
        return "".join(slist)
    # end of create_header_relay-------------------------------------------------------------------
    
    # this function creates the header of a node- packet
    # the length of the useful data has to be provided
    def create_header_node(self, packet_id, length = 0, last_in_burst = False):
        header = ['', '', '', '', '']
        # set the source flag in the first byte of the header
        if self.RQA == self.MY_REQUEST: # node_id == A
            first = 0 | self.QA
        else:   # node_id == B
            first = 0 | self.QB
        if last_in_burst == True:
            first |= self.LIB   # set LIB bit
        else:
            pass    # do not set LIB bit
        header[0] = pack('!B', first)
        header[1:2] = pack('!H', packet_id)
        header[3] = pack('!B', length)
        slist = [str(elt) for elt in header]    # does (str(header[0]) + str(header[1]) + str(header[2]) + str(header[3]))
        return "".join(slist)
    # end of create_header_node-------------------------------------------------------------------
# end of class protocol_header

# class for holding the functionality being specific for the relay

class network_code:
    # this function performs the network coding
    # paramters:
    # payload_A: the part of the packet from A (as a string) which should be network-coded
    # payload_B: the part of the packet from B (as a string) which should be network-coded
    def network_code(self, payload_A = '', payload_B=''):
        size_a = len(payload_A)
        size_b = len(payload_B)
        # adjust both strings to the same length
        if size_a == size_b:
            pass    # no enlargment neccessary
        elif size_a > size_b:
            payload_B = self.padding(payload_B, size_a - size_b) #payload_B must be enlarged
        else:   #size_a < size_b and payload_A must be enlarged
            payload_A = self.padding(payload_A, size_b - size_a)

        return self.xor(payload_A, payload_B)    # networkcode via xor between the two messages

    def network_decode(self, payload = '', mypacket=''):
        length_coded = self.xor(mypacket[0], payload[0])    #network decode the length of the useful data
        length = unpack('!B',  length_coded)[0]
        real_length = len(payload[1:])
        mylength = unpack('!B',  mypacket[0])[0]
        if real_length > mylength: 
            mypacket = self.padding(mypacket, real_length - mylength)
        if (len(mypacket[1:]) == 0) and (len(payload[1:]) == 0):
            return "" # nothing to decode, both packets were empty
        if len(mypacket[1:]) == len(payload[1:]):
            coded_data = self.xor(mypacket[1:],  payload[1:])
        else:
            print "Error: false padding!"
        data = self.remove_padding(coded_data, length)
        return (str(length_coded) + data)

    # this function adds 0s to a string in order to prepare it for networkcoding
    # paramters:
    # res:      the string which should get the additional 0s at its end
    # number:   the number of 0s which should be added to res
    def padding(self, res='', number=0):
        return (res + zeros(number,int8).tostring())

    #remove padding which was added before networkcoding
    def remove_padding(self, payload = '', size=0):
        return payload[0:size]

    # this function does a bytewise xor operation of two given input strings in order to networkcode them
    # paramters:
    # payload_A: the first part of the input data which should be combined with the second part by byte-wise XOR
    # payload_B: the second part of the input data which should be combined with the first part by byte-wise XOR
    def xor(self, payload_A = '', payload_B=''):
        res = ''
        if payload_A == '' or payload_B == '':
            print "Error: There is not data to XOR!"
            print payload_A
            print payload_B
        i = frombuffer(payload_A,  dtype = byte)
        j = frombuffer(payload_B,  dtype = byte)
        try:
            res = (bitwise_xor(i, j)).tostring()
        except:
            print "Error: arguments do not have equal length!"
            raise ValueError
        return res
# end of class network_code

class channel_code:
    SIZE_DATA = 223 # 6 Byte header + 213 Byte payload + 4 Byte CRC
    SIZE_CODED_DATA = 255
    SIZE_REQUEST = 8    # 4 Byte header + 4 Byte CRC
    SIZE_CODED_REQUEST = 12
    
    code_nr = 0
    
    def __init__(self):
        self.my_codec_data = Codec(self.SIZE_CODED_DATA, self.SIZE_DATA)
        self.my_codec_request = Codec(self.SIZE_CODED_REQUEST, self.SIZE_REQUEST)
        try:
            temp = self.my_codec_data.encode('5'*self.SIZE_DATA)
            self.my_codec_data.decode(temp)
            print "Channel Codes set up!"
        except:
            print "Error: Channel Code does not work!"
            sys.exit(1)
        
    # channel encodes the data
    def channel_encode(self, payload_with_crc):
        if self.code_nr == 0:   # no channel coding
            return payload_with_crc
        elif self.code_nr == 1: # RS
            try:
                if len(payload_with_crc) == self.SIZE_DATA:
                    payload_coded = self.my_codec_data.encode(payload_with_crc)
                elif len(payload_with_crc) == self.SIZE_REQUEST:
                    payload_coded = self.my_codec_request.encode(payload_with_crc)
                else:
                    raise ValueError
            except ValueError:
                print "Error: Cannot encode packet due to wrong size!"
                print "Size is %d" % len(payload_with_crc)
                print "data size %d" % self.SIZE_DATA
                payload_coded = ""
            return payload_coded
        else:
            print "ERROR: no channel code with this code number defined!"
        return ""
        
    def channel_decode(self, payload_with_crc):
        if self.code_nr == 0:   # no channel coding
            return payload_with_crc
        elif self.code_nr == 1: # RS
            try:
                if len(payload_with_crc) == self.SIZE_CODED_DATA:
                    payload_with_crc = self.my_codec_data.decode(payload_with_crc)[0]
                elif len(payload_with_crc) == self.SIZE_CODED_REQUEST:
                    payload_with_crc = self.my_codec_request.decode(payload_with_crc)[0]
                else:
                    # wrong size detected
                    print "Cannot decode packet due to wrong size!"
                    print "size is: %d" % len(payload_with_crc)
                    payload_with_crc = ""
            except:
                print "Too many errors or erasures!"
                print payload_with_crc
                payload_with_crc = ''
            return payload_with_crc
        else:
            print "ERROR: no channel code with this code number defined!"
        return ""

    # add the channel encoded header
    def add_physical_header(self, payload):
        payload_len = len(payload)
        if payload_len == self.SIZE_CODED_DATA:
            val = 0xffff
        else:   # request
            val = 0x0000
        #print "offset =", whitener_offset, " len =", payload_len, " val=", val
        return ''.join((pack('!HH', val, val), payload))

# the class network_member is the top level class for the relay and the node class
class network_member:
    # references to the flow graphs
    tb_tx = None
    tb_rx = None
    
    # variables for enabling communication between this process and a GUI (if there is one)
    parent_id = None
    write_pipe = None
    
    # variables for keeping fixed design parameters
    HEADER_LEN_NODE = 4
    HEADER_LEN_RELAY = 4
    HEADER_LEN_RELAY_NC = 6
    
    # variables for keeping statistical information
    n_rcvd = 0
    n_right = 0
    data_rcvd = 0
    data_trans = 0
    n_trans = 0
        
    # variables for controlling the update frequency of statistical information displayed in the GUI
    UPDATE = 100                            # if update_count reaches UPDATE an update is performed
    update_count = 0                     # counter for controlling the update frequency of the gui
    
    # instace of the network_code class for enabling the usage of network coding
    mynetworkcoder = network_code()
    mychannelcoder = channel_code()
    
    # time measurement
    start_time = 0
    
    vlc = None
    
    # basic set-up criteria
    NETWORK_CODING = True
    output_buffer = []
    verbose = False
    
    def __init__(self, write_pipe, gui, channel_code_nr):
        self.write_pipe = write_pipe
        signal.signal(signal.SIGTERM, self.stop_execution)
        if gui is not None:
            self.parent_id = os.getppid()
        self.mychannelcoder.code_nr = channel_code_nr
        #print "Kanalcode Nr. " + str(channel_code_nr)

    def update_statistics(self, timeouts = 0):
        update = (str(self.n_rcvd) + ' ' + str(self.n_right) + ' ' + str(self.n_trans) + ' ' + str((time.time())-self.start_time) + ' ' + str(self.data_rcvd) + ' ' + str(self.data_trans) + ' ' + str(timeouts))
        try:
            os.write(self.write_pipe, str(update))
        except:
            os.write(int(sys.argv[0]), str(update))
        if self.verbose:
            print "I write to pipe nr. " + str(self.write_pipe)
            print "wrote into pipeline: " + str(update)
        try:
            os.kill(self.parent_id, signal.SIGCONT)    # inform the GUI that there is an update available
        except:
            os.kill(os.getppid(), signal.SIGCONT)
        
    # stops the execution
    def stop_execution(self, signum, frame):
        print "Got SIGTERM, stopping."
        signal.alarm(0) # reset timeout
        # perform last update of statistic
        try:
            self.update_statistics(self.timeouts_all)   #this will fail for a node as there is no timeout-counter
        except:
            self.update_statistics()
        print "Last update done!"
        time.sleep(1)   # give the scheduler some time to send out the last packets in the buffer
        try:
            self.tb_tx.stop()
        except:
            pass
        try:  # a node does not keep a reference to its receive flow graph
            self.tb_rx.stop()
        except:
            pass
        sys.exit(0)
    
    # expects a packet
    def wrap_in_frame(self, payload):
        if self.mychannelcoder.code_nr == 0:
            length= len(payload)
            if length <= 8: #12 - 4
                # this is a node request
                diff = 12 - len(payload) - 4
                payload += zeros(diff,int8).tostring()
            elif length <= 251: #255 - 4
                # data packet
                diff = 255 - len(payload) - 4
                payload += zeros(diff,int8).tostring()
            else:
                "Error: Data too long!"
        elif self.mychannelcoder.code_nr == 1:
            length= len(payload)
            if length == (self.mychannelcoder.SIZE_REQUEST - 4):
                # this is a node request
                pass
            elif length <= (self.mychannelcoder.SIZE_DATA - 4):
                # data packet
                diff = self.mychannelcoder.SIZE_DATA - len(payload) - 4
                payload += zeros(diff,int8).tostring()        
            else:
                "Error: Data too long!"
        else:
            print "ERROR: cannot wrap in frame because selected channel code is not configured here!"
        
        # append the CRC
        payload_with_crc = gru.gen_and_append_crc32(payload)
        # channel encode
        payload_coded = self.mychannelcoder.channel_encode(payload_with_crc)
        
        # add the channel encoded header
        payload_with_head = self.mychannelcoder.add_physical_header(payload_coded)
        return payload_with_head
        
# end of class network_member

class relay (network_member):
    TIMEOUTLIMIT = 2      #if this limit is exceeded we transmit a new request as we exepect package(s) was/were lost
    MAX_TIMEOUTS = 10   # if the variable timeouts exceeds this limit we assume that the connection is totally broken and the program is interrupted
    NEXT_AIM = {'A': 'B', 'B': 'A'}      # list which defines the order of requests to be sent to the different nodes
    INITIAL_AIM = 'A'
    current_aim = 'A'                       # first time request for data transmission is sent to A by default
    myheader = protocol_header()    # get an instance of the protocol header class
    timeouts = 0
    timeouts_all = 0
    buffered_data = False
    packet_buffer_A = []
    packet_buffer_B = []
    alarm_requested = False     # flag to indicate if an ALARM signal is currently requested

    gui = None
    test_node = None
    test_pkt = 0

    last = 0

    # basic set-up criterias of the network
    BIDIRECTIONAL = True
    POINT2POINT = False
    
    def __init__(self, tx, nc, bidirectional, point2point, gui, write_pipeline, timeout, channel_code_nr):
        network_member.__init__(self, write_pipeline, gui, channel_code_nr)
        global verbose
        self.verbose = verbose
        self.current_aim = self.INITIAL_AIM
        # for receiver timeout:
        signal.signal(signal.SIGALRM, self.timeout_handler)
        self.tb_tx = tx
        self.gui = gui
        self.NETWORK_CODING = nc
        self.BIDIRECTIONAL = bidirectional
        self.POINT2POINT = point2point
        self.TIMEOUTLIMIT = timeout
        if self.verbose:
            print "network coding is " + str(self.NETWORK_CODING)
            print "bidirectional is " + str(self.BIDIRECTIONAL)
            print "point to point is " + str(self.POINT2POINT)
            print "ran through init"

    # this function is called when a packet was received
    def rx_callback(self, payload_coded):
        signal.alarm(0)    #package recognised, therefore stop timeout
        verb = self.verbose
        if verb:
            print "Relay got a packet!"

        #update statistical information
        self.n_rcvd += 1         # count number of received packets
        
        payload_with_crc = self.mychannelcoder.channel_decode(payload_coded)
        ok, payload = gru.check_crc32(payload_with_crc)
        
        if ok:
            self.n_right += 1    # count number of correctly received packets
            #print str(time.time()-self.start_time)
            #self.stop_execution(None, None)
            if verb:
                print "packet was ok!"
            self.timeouts = 0    # we got a correct packet, therefore we assume that the link is working properly
            self.data_rcvd += len(payload) - self.HEADER_LEN_NODE - 2 # two byte padding
            first = self.myheader.analyse_header(unpack('!B', payload[0])[0])
            if first[4] == True:    # source of data is A
                self.packet_buffer_A.append(payload)
                if self.packet_buffer_B != []:
                    self.buffered_data = True
            elif first[5] == True:  # source of data is B
                self.packet_buffer_B.append(payload)
                if self.packet_buffer_A != []:
                    self.buffered_data = True
            else:
                print "Error: data has no valid source!"
                
            if self.myheader.check_for_burst_end(unpack('!B', payload[0])[0]) == True:   # the node will not send more packets during this burst
                if verb:
                    print "End of burst detected!"
                if (self.BIDIRECTIONAL == True) or (self.NETWORK_CODING == True):   # network coding requires packets from at least 2 sources
                    # change the aim for the next request
                    self.current_aim = self.NEXT_AIM[self.current_aim]
                    if verb:
                        print "Changed my aim!"
                #here we have 3 possiblities
                #1. we can directly forward the packet
                #2. we can request another packet from the other node to apply network coding
                #3. we can combine the packet with an earlier received packet by network coding and than send out this new packet
                if self.NETWORK_CODING == True:
                    if self.buffered_data == True:    #we have packet(s) in the buffer with which we can combine the ones from the last burst
                        self.send_data()
                    else:
                        self.send_request()          #get data from the other node
                elif self.POINT2POINT == True:
                    # do nothing with received data
                    self.send_request() # just requesting the next packet burst
                else:       # send data without manipulating it
                    self.send_data()
                
            else:   # more data to come in this burst
                pass # just wait for the rest of the burst
        else:
            #CRC signals that there was an error, do not rerequest data as it could be in the middle of a burst
            pass
            #self.send_request()
            #print payload
        
        try:
            pid = unpack('!H', payload[1:3])[0]    # this is also done when the CRC is incorrect, therefore it may fail with a malformed packet
        except:
            pid = 9999  # unused value for marking the error
            
        if verb:
            print "ok = %5s  ID = %4d  n_rcvd = %4d  n_right = %4d" % (ok, pid, self.n_rcvd, self.n_right)
        self.update_count += 1
        if (self.update_count == self.UPDATE) and (self.gui is not None):
            self.update_statistics(self.timeouts_all)
            self.update_count = 0
        # start the timeout
        signal.alarm(self.TIMEOUTLIMIT)
        return

    measure = 0
    def send_pkt(self, payload='', eof=False):
        try:
            #print (time.time() - self.last)
            #self.last = time.time()
            res = self.tb_tx.txpath.send_pkt(payload, eof)
        except: # for a test there is no flow graph
            self.output_buffer.append(payload)
        self.n_trans += 1
        self.update_count += 1
        if (self.update_count == self.UPDATE) and (self.gui is not None):
            self.update_statistics(self.timeouts_all)
            self.update_count = 0
        if self.verbose:
            print "Sent a packet! "
        
        global measurement
        if measurement == True:
            self.measure += 1
            if self.measure == 20000:
                self.stop_execution(None, None)
        return res

    # this function initiates a single request for data
    def send_request(self):
        if self.current_aim == 'A':
            payload = self.myheader.create_header_relay(str(pack('!B', 0)), True,  False)
        elif self.current_aim == 'B':
            payload = self.myheader.create_header_relay(str(pack('!B', 0)), False,  True)
        else:
            print "This should not happen!"
            print "Current aim is: " + str(self.current_aim)
        # wrap in physical frame
        payload_coded = self.wrap_in_frame(payload)
        self.send_pkt(payload_coded)
        if self.verbose:
            print "packet with pure request sent out to " + self.current_aim
        return

    # this function creates a singe data packet
    # parameters:
    # payload_A: this parameter can have two meanings
    #                    1. nc == True:  the payload of the packet from node A
    #                    2. nc == False: the payload of the packet which has to be send, can be from node A or B
    # nc:          should the packet be a network-coded one?
    # request:  should the packet header include a request?
    # payload_B: this paramter is only necessary if nc == True as then it will hold the payload of the packet from node B, otherwise it will be ignored
    def assemble_data_pkt(self, payload_A, nc, request, payload_B=''):
        # determine if we should request a burst and if so, who should be requested to send data
        if request == True:
            if self.current_aim == 'A':
                req_a = True
                req_b = False
            elif self.current_aim == 'B':
                req_a = False
                req_b = True
            else:
                print "This should not occore!"
                self.stop_execution(None, None)
        else:
            req_a = False
            req_b = False
            
        if nc == False:
            first = self.myheader.analyse_header(unpack('!B', payload_A[0])[0])
            if first[4] == True:
                origin = 'A'
            elif first[5] == True:
                origin = 'B'
            else:
                print "Error: data has no origin!"
            header = self.myheader.create_header_relay(payload_A[3], req_a, req_b, payload_A[1:3], '', False, origin)
            length = unpack('!B', payload_A[3])[0]
            payload = header + payload_A[self.HEADER_LEN_NODE:length+self.HEADER_LEN_NODE]  # assemble the new packet
            self.data_trans += len(payload) - self.HEADER_LEN_RELAY # header is 4 byte long
        else:
            encode = self.mynetworkcoder.network_code
            new_length = encode(payload_A[3], payload_B[3])
            header = self.myheader.create_header_relay(new_length, req_a, req_b, payload_A[1:3], payload_B[1:3], True)
            if (len(payload_A[4:]) == 0) and (len(payload_B[4:]) == 0):
                new_payload = ""    # both packets contain no data, e.g. both files have been transmitted => there is not data to combine anymore
            else:
                length_a = unpack('!B', payload_A[3])[0]
                if self.verbose:
                    print "length data of A: " + str(length_a)
                length_b = unpack('!B', payload_B[3])[0]
                if self.verbose:
                    print "length data of B:" + str(length_b)
                new_payload = encode(payload_A[self.HEADER_LEN_NODE:length_a + self.HEADER_LEN_NODE], payload_B[self.HEADER_LEN_NODE:length_b + self.HEADER_LEN_NODE])
                if (len(new_payload) is not length_a) and (len(new_payload) is not length_b):
                    print "Error in network coding!"
            payload = header + new_payload      # assemble the new packet
            self.data_trans += len(payload) - self.HEADER_LEN_RELAY_NC    # header has 6 byte length
            
        payload = self.wrap_in_frame(payload)

        if self.verbose:
            print "packet created"
        return payload
    
    # function to set attribute tb_rx
    def set_tb_rx(self, rx):
        self.tb_rx = rx
    
    def send_data(self):
        assemble = self.assemble_data_pkt   # making a local reference to the function
        list = []   # a list for holding the packets which are to be sent out
        buffer_a = self.packet_buffer_A
        buffer_b = self.packet_buffer_B
        i = 0
        if self.NETWORK_CODING:
            if len(self.packet_buffer_A) >= len(self.packet_buffer_B):
                more_data = self.packet_buffer_A
                less_data = self.packet_buffer_B
            else:
                more_data = self.packet_buffer_B
                less_data = self.packet_buffer_A
            num = range(len(more_data) - 1)
            for i in num:
                try:
                    data = less_data[i] # this will fail with an IndexError if there is no more data
                    list.append(assemble(buffer_a[i], True, False, buffer_b[i]))
                except IndexError:
                    # there is no more data for network coding
                    list.append(assemble(more_data[i], False, False))
            # the last packet has to contain a request
            try:
                data = less_data[i] # this will fail with an IndexError if there is no more data
                list.append(assemble(buffer_a[i], True, True, buffer_b[i]))
            except IndexError:
                # there is no more data for network coding
                list.append(assemble(more_data[i], False, True))
        else:   # no network coding
            if len(buffer_a) == 0:   # stored data is from B
                buffered_data = buffer_b
            else:   # stored data is from A
                buffered_data = buffer_a
            num = len(buffered_data)    # the last packet has to be treated differently
            # no network coding and no request
            nc_list = [False]*num
            request_list = [False] * num
            # the last packet has to be treated differently
            request_list[-1] = True     # the last packet in the burst has to contain a request for new data
            list = map(assemble, buffered_data, nc_list, request_list)
            
        self.buffered_data = False
        self.packet_buffer_A = []
        self.packet_buffer_B = []
        # send the data out
        send = self.send_pkt
        map(send, list)
        # all data should be sent out
        return True
    
    # this function is called when a timeout occures
    def timeout_handler(self, signum, frame):
        #print 'Signal handler called with signal ' + str(signum)
        self.timeouts_all += 1
        print "Timeout occured!"
        print "Node which did not respond has ID: " + str(self.current_aim)
        self.timeouts += 1
        if self.timeouts == self.MAX_TIMEOUTS:
            print "termination of connection due to timeouts"
            self.send_pkt(eof=True)
            self.stop_execution(None, None) # it is also used as a signal handler and therefore it expects two arguments
        if (self.packet_buffer_A != []) or (self.packet_buffer_B != []):    # if there is buffered data send it out
            if self.POINT2POINT is not True:    # only send the data if this is not in the point to point communication scenario
                self.send_data()
            else:
                self.send_request()
        else:   # no data to send, therefore send a request
            self.send_request()
        signal.alarm(self.TIMEOUTLIMIT)
# end of class relay

class node (network_member):
    NODE_ID = 'A'   # the id of the node, NOTE: if the node is intended to send data the assigned id must be part of NEXT_AIM from class relay as it otherwise won't be allowed to send any data

    RECEIVE_ID_LOWER_LIMIT = None
    RECEIVE_ID_UPPER_LIMIT = None
    SEND_DATA_ID_LOWER_LIMIT = None
    SEND_DATA_ID_UPPER_LIMIT = None
    REQUEST_ID = None
    
    DATA_SIZE_NO_CHANNEL_CODE = 245   # 255 - 6 (header) - 4 (CRC)
    DATA_SIZE_RS_CODE = 213                     # 223 - 6 (header) - 4 (CRC)

    # possible types of transfers, the active one is selected in __init__
    FILE_TRANSFER = False
    VIDEO_STREAMING = False
    TRANSFER_RANDOM_DATA = False
    TRANSFER_CONSTANT_DATA = False
    
    DIRECT_LINK = False
    
    # variables for controlling the size of packet bursts
    BURST_SIZE = 10                     # if the number of continuasly sent packets reaches BURST_SIZE transmission is stopped
    burst_counter = 0
    
    source = None   # source for transmission
    output = None
    last_packets = None
    last_node_id = 0
    myheader = None
    
    # variables for keeping statistical information
    n_other_aim = 0
    n_other_node = 0
    gui = None
    test = False
    
    def __init__(self, tb, type_of_transfer,  node_id, nc, direct_link, gui = None, write_pipeline=None, burst_size = 1, channel_code_nr = 0, bidirectional = True, port=1234):
        network_member.__init__(self, write_pipeline, gui, channel_code_nr)
        global verbose
        self.verbose = verbose
        self.tb_tx = tb
        
        if type_of_transfer == 'F':
            self.FILE_TRANSFER = True
            if gui is None: # started from command line
                self.source = open("./transfer_file.txt", 'r')  # take default file as the user cannot have specified what file to take
            else:   # started from gui
                try:
                    self.source = open(gui.file_source.get(), 'r')  # this can result in an error
                    print "reading from file:" + gui.file_source.get()
                except IOError:
                    if (bidirectional == True) or (bidirectional == False and node_id == 'B'):
                        print "File not found!"
                        raise IOError  # end

            self.output = open("./transferred_file", 'w')
            print "Info: Transferring a file!"
        elif type_of_transfer == 'V':
            try:
                if (bidirectional == True) or (bidirectional == False and node_id == 'B'):
                    Popen(["vlc", "udp://@127.0.0.1:" + str(port)])
            except:
                print("ERROR: VLC could not be opened!")
                raise IOError
            self.VIDEO_STREAMING = True
            try:
                self.source = open("temp.video", "r")
            except:
                if (bidirectional == True) or (bidirectional == False and node_id == 'B'):
                    print("ERROR: Video File not found!")
                    raise IOError
            self.output = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            print "Info: Transferring a video stream!"
        elif type_of_transfer == 'R':
            self.TRANSFER_RANDOM_DATA = True
            self.source = open("/dev/urandom", 'r')     # use a non-blocking random source
            print "Info: Transferring random data!"
        elif type_of_transfer == 'C':
            self.TRANSFER_CONSTANT_DATA = True
            print "Info: Transferring constant data!"
        else :   #default
            print "Error: no (valid) type of transfer selected!"
            print "Error: Nothing to transfer!"
            raise KeyboardInterrupt
            
        if node_id is not None:
            self.NODE_ID = node_id
            if (node_id in relay(None, None, None, None, None, None, None, channel_code_nr).NEXT_AIM) == False:
                print "Warning: this node will never be allowed to send!"
            self.myheader = protocol_header(node_id)
        else:
            print "Error: No node-ID given!"
        
        if node_id == 'A':
            self.RECEIVE_ID_LOWER_LIMIT = 32769 #129
            self.RECEIVE_ID_UPPER_LIMIT = 65535 #255
            self.SEND_DATA_ID_LOWER_LIMIT = 1 #1
            self.SEND_DATA_ID_UPPER_LIMIT = 32767 #127 
            self.REQUEST_ID = 0
            print "start-up as node A"
        elif node_id == 'B':
            self.RECEIVE_ID_LOWER_LIMIT = 1 #1
            self.RECEIVE_ID_UPPER_LIMIT = 32767 #127
            self.SEND_DATA_ID_LOWER_LIMIT = 32769 #129
            self.SEND_DATA_ID_UPPER_LIMIT = 65535 #255
            self.REQUEST_ID = 32768 #128
            print "start-up as node B"
        else:
            print "this node ID is not configured!"
            sys.exit(1)
        
        self.last_packets = {self.SEND_DATA_ID_LOWER_LIMIT:''}
        self.packet_id = self.SEND_DATA_ID_LOWER_LIMIT   # begin to send with the smallest possible ID
        self.gui = gui  # keep a reference to the gui in order to be able to initiate an update of displayed results
        self.DIRECT_LINK = direct_link
        self.NETWORK_CODING = nc
        self.BURST_SIZE = burst_size
        
        self.channel_code_nr = channel_code_nr
        
        if self.verbose:
            print "burst size: " + str(burst_size)
        print "Write pipeline: " + str(write_pipeline)
            
    # this method is called when the instance of the class is destroid
    def __del__(self):
        # close open files
        if self.FILE_TRANSFER or self.VIDEO_STREAMING:
            self.source.close()
            self.output.close()
            
    # this function is called when a packet was received
    def rx_callback(self, payload_coded):
        verb = self.verbose
        if verb:
            print "Node got a packet!"
            
        payload_with_crc = self.mychannelcoder.channel_decode(payload_coded)
        ok, payload = gru.check_crc32(payload_with_crc)
            
        try:
            pid = unpack('!H', payload[1:3])[0]    # with a malformed packet this may result in an error!
        except:
            pid = 9999  # unused value for marking the error
            ok = False

        #update statistical information and respond to a recognised request for data
        self.n_rcvd += 1
        if ok:
            self.n_right += 1
            header_first = self.myheader.analyse_header(unpack('!B', payload[0])[0])
            
            if header_first[0]:   #if the packet was sent by the relay
                if header_first[1]:   #if it is networkcoded
                    # the packet-id we have to look at depends on which node-id we have
                    if self.NODE_ID == 'A':
                        key = int(unpack('!H', payload[1:3])[0])
                    elif self.NODE_ID == 'B':
                        key = int(unpack('!H', payload[3:5])[0])
                    else:
                        print "This should not happen! Configured NODE-ID not valid."
                        sys.exit(1)
                    if verb:
                        print "the packet has ID-A: %4d and ID-B: %4d" % (unpack('!H', payload[1:3])[0], unpack('!H', payload[3:5])[0])
                    # know in key the number of our own packet is stored which is part of the networkcoded packet
                    if self.last_packets.has_key(key) == True:
                        our_payload = self.last_packets[key][3:]     #get the payload of our own packet, length inclusive
                        data = self.mynetworkcoder.network_decode(payload[5:], our_payload)
                        length = unpack('!B', data[0])[0]
                        self.data_rcvd += length
                        self.store_data(data[1:length+1], pid)
                    else:
                        print "Warning: could not decode packet as I have not stored a packet with ID %4d" % (key)
                elif (pid<= self.RECEIVE_ID_UPPER_LIMIT) and (pid >= self.RECEIVE_ID_LOWER_LIMIT): # we are the aim
                    #do something with the received data
                    # data can be stored as it is
                    if verb:
                        print "The packet was sent to us!"
                    length = unpack('!B', payload[3])[0]
                    self.store_data(payload[self.HEADER_LEN_RELAY:length+self.HEADER_LEN_RELAY], pid)
                    self.data_rcvd += length
                    if verb:
                        print "the packet has ID: %5d" % (pid)
                elif pid == self.REQUEST_ID:
                    if verb:
                        print "I got a pure request!"
                        # nothing to do as there is no data
                else:                       #it is our own packet which was sent by the relay
                    if verb:
                        print "It was a packet for another one!"
                        print "the packet has ID: %5d" % (pid)
                    self.n_other_aim += 1
                # check weather we are requested to send data
                if header_first[2]:
                    if verb:
                        print "My request flag is set!"
                    self.send_data()
            else:
                if verb:
                    print "Got a packet which was not sent by the relay!"
                self.n_other_node += 1
                if self.DIRECT_LINK == True:
                    self.last_node_id = pid    # keep track of received packet
                    length = unpack('!B', payload[3])[0]
                    self.store_data(payload[self.HEADER_LEN_NODE:length+self.HEADER_LEN_NODE], pid)
                    self.data_rcvd += length
                else:
                    pass                        #no combination of packets from relay and originally sent package from other node
        else:
            if verb:
                print payload
            try:
                header_first = self.myheader.analyse_header(unpack('!B', payload[0])[0])
                if (header_first[2] == True) and (pid == self.REQUEST_ID):
                    self.send_data()
                    print "Sent data although CRC was incorrect, but request id and request flag indicated this behaviour!"
                else:
                    print "Nothing done with received data as CRC was incorrect!"
            except:
                print "Got a malformed packet, nothing done with its content!"
        self.update_count += 1
        if (self.update_count == self.UPDATE) and (self.gui is not None):
            self.update_statistics()
            self.update_count = 0
        if verb:
            print "ok = %5s  ID = %4d  n_rcvd = %4d  n_right = %4d n_other_node = %4d  n_other_aim =  %4d  n_for_me = %4d" % (ok, pid, self.n_rcvd, self.n_right, self.n_other_node,  self.n_other_aim,  self.n_right - (self.n_other_aim + self.n_other_node))
    # end of rx_callback----------------------------------------------------------------

    def send_pkt(self, payload='', eof=False):
        self.n_trans += 1
        if self.channel_code_nr == 0:
            self.data_trans += self.DATA_SIZE_NO_CHANNEL_CODE
        elif self.channel_code_nr == 1:
            self.data_trans += self.DATA_SIZE_RS_CODE
        else:
            print ("ERROR: number of info-bytes not defined!")
        self.update_count += 1
        if (self.update_count == self.UPDATE) and (self.gui is not None):
            self.update_statistics()
            self.update_count = 0

        try:
            res = self.tb_tx.txpath.send_pkt(payload, eof)
        except:
            res = True
            self.output_buffer.append(payload)
        return res

    # generate and send packets
    # be careful: this function uses a lot of performance improvement techniques from http://wiki.python.org/moin/PythonSpeed/PerformanceTips
    def send_data(self):
        i = 0
        list = []
        burst_size = self.BURST_SIZE
        create_header = self.myheader.create_header_node
        data_source = self.get_data
        send = self.send_pkt
        amount = range(burst_size)
        local_packet_id = self.packet_id
        nc = self.NETWORK_CODING
        upper_limit = self.SEND_DATA_ID_UPPER_LIMIT
        lower_limit = self.SEND_DATA_ID_LOWER_LIMIT
        verb = self.verbose
        for i in amount:
            data = data_source()
            if i < (burst_size - 1):
                header = create_header(local_packet_id, len(data), False)    # use local reference to function
            else:   # last packet in burst
                header = create_header(local_packet_id, len(data), True)        # use local reference to function
            payload = header + data
            if nc: # network coding enabled?
                self.last_packets[local_packet_id] = payload     #keep track of the former sent packets
            payload = self.wrap_in_frame(payload)
            list.append(payload)
            if verb:
                print "packet created"
                
            # increment the packet ID and check for not exceeding the limit
            local_packet_id += 1
            if local_packet_id > upper_limit:
                local_packet_id =  lower_limit
        self.packet_id = local_packet_id # save value
        
        # send data out
        map(send, list)
        if verb:
            print "burst sent!"
        return

    # this function gets the data which should be sent out
    def get_data(self):
        if (self.FILE_TRANSFER == True) or (self.TRANSFER_RANDOM_DATA == True) or self.VIDEO_STREAMING == True:
            if self.channel_code_nr == 0: # no channel coding
                return self.source.read(self.DATA_SIZE_NO_CHANNEL_CODE)
            elif self.channel_code_nr == 1:   #RS
                return self.source.read(self.DATA_SIZE_RS_CODE)
        elif self.TRANSFER_CONSTANT_DATA == True:
            if self.channel_code_nr == 0: # no channel coding
                res = '5'*self.DATA_SIZE_NO_CHANNEL_CODE
            elif self.channel_code_nr == 1:   #RS
                res = '5'*self.DATA_SIZE_RS_CODE
            else:
                print "ERROR: no such channel code!"
            return res
        else:
            print "Error: No data to send!"
            return ''

    # this function stores the data which was received
    def store_data(self, data = '', pid = 0):
        if (self.DIRECT_LINK == False) or ((self.DIRECT_LINK == True) and (pid != self.last_node_id)):  # only store data if it has not been stored before
            if self.VIDEO_STREAMING == True:
                self.output.sendto(data, ("localhost", 1234))
                if self.verbose:
                    print "Sent data to VLC media player!"
            elif self.FILE_TRANSFER == True:
                self.output.write(data)
                if self.verbose:
                    print "Wrote data into file!"
            elif self.TRANSFER_CONSTANT_DATA == True:
                if self.verbose:
                    print data
                if self.test:
                    self.output_buffer.append(data)
            else:
                print "Nothing to do with received data!"
                print data
        else:
            print "Not storing data as it has already been stored."
        if (len(data) is not self.DATA_SIZE_NO_CHANNEL_CODE) and (len(data) is not self.DATA_SIZE_RS_CODE):
            print "Data has invalid size of: " + str(len(data))
        return True
# end of class node

# /////////////////////////////////////////////////////////////////////////////
#                                   main
# /////////////////////////////////////////////////////////////////////////////
    # this function expects the following parameters:
    # relay: TRUE = This is the relais, FALSE = this is a node
    # side: the side on which the daughterboard is installed on the USRP
    # freq: the transmission and reception frequency
    # rate: the transmission rate
    # tx_gain: transmitter gain
    # rx_gain: receiver gain
    # nc: True means network coding is enabled, False means it is disabled
    # bidirectional: only relevant for a relay
    # benchmark: only relevant for a relay
    # gui: reference to the GUI, if there is no GUI: None
    # pipe: write pipeline to the process running the GUI, used for updating the displayed statistical information; if there is no GUI: None
    # timeout: value for the timeout in seconds, only relevant for a relay
    # node_id: when this is a node, an ID has to be specified; possible values are A and B
    # burst. number of packets inside a burst
    # direct_link: True = direct link used, False = direct link ignored, only relevant for a node
    
def main(RELAY, side, freq, rate, tx_gain, rx_gain, transmission_type, nc, direct_link, bidirectional, benchmark, gui, write_pipeline, timeout, node_id, burst_size, channel_code_nr):
        
    # Using fixed parameters from the parameter class
    myparameters = parameter(side, freq, rate, tx_gain, rx_gain)
        
    # build the transmit graph
    mods = modulation_utils.type_1_mods()       # all types of modulation
    options_tx = myparameters.set_tx_parameters()

    tb_tx = mytx_top_block(mods[options_tx.modulation], options_tx)

    if (gui is not None) and (write_pipeline is None):
        print "Fatal Error, no write pipeline!"
        sys.exit(1)

    if (gui is None):
        print "No GUI detected!"

    if RELAY:
        # as we are the relay initialising as relay
        print "start-up as relay"
        myself = relay(tb_tx, nc, bidirectional, benchmark, gui, write_pipeline, timeout, channel_code_nr)
    else:   # we are a node
        myself = node(tb_tx, transmission_type, node_id, nc, direct_link, gui, write_pipeline, burst_size, channel_code_nr, bidirectional)

    # build the receive graph
    demods = modulation_utils.type_1_demods()   # all types of demodulation
    options_rx = myparameters.set_rx_parameters()

    tb_rx = myrx_top_block(demods[options_rx.modulation], myself.rx_callback, options_rx)

    sys.argv[0] = write_pipeline
    print sys.argv[0]

    if RELAY == True:
        myself.set_tb_rx(tb_rx)
    
    r = gr.enable_realtime_scheduling()
    if r != gr.RT_OK:
        print "Warning: failed to enable realtime scheduling"
    else:
        print "Info: Enabled realtime scheduling."

    try:
        # start flow graphs
        tb_rx.start()
        print "Receiving flow graph started"
        tb_tx.start()
        print "Transmission flow graph started"
    except:
        print "ERROR: no flow graphs started!"
    
    myself.start_time = time.time()     # save time of start-up
    
    if RELAY == True:
        myself.send_request()   # kick-off
        signal.alarm(timeout) # start first timeout

    # there is noting which keeps the process alive, so we have to wait here until the communication- thread has been terminated
    try:
        tb_rx.wait()
    except:
        pass

if sys.argv[0] == "GUI":
    pass    # there is a gui which will invoke the main-function when this is neccessary
elif __name__ == '__main__':
    info = dict()
    try:
        relay = True                    # true = station is relay, false = station is node
        side = 'B'                      # side of the USRP daughter-board, valid values are 'A' and 'B'
        freq='5375M'
        rate='512k'
        tx_gain='20'
        rx_gain='66'
        transmission_type='C'      # valid values are: 'C': constant data, 'F': file, 'V': video, 'R': random values
        network_coding = True
        direct_link = False
        bidirectional = True
        benchmark = False
        timeout = 1
        node_id = 'A'                   # valid values are 'A' and 'B'
        burst_size = 1
        channel_code_nr = 1
        main(relay, side, freq, rate, tx_gain, rx_gain, transmission_type, network_coding, direct_link, bidirectional, benchmark, None, None, timeout, burst_size, node_id, channel_code_nr)
    except KeyboardInterrupt:
        pass
else:
    print "This should not happen!"

