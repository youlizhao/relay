#!/usr/bin/env python

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

from Tkinter import *
from tkFileDialog import *
from subprocess import Popen
sys.argv = [""]
sys.argv[0] = "GUI" # clue to distinguish in the alternating module whether there is a GUI or not
from relaying import *
import os   # operating system functionality (e.g. signals)
import re   # regular expressions
import ctypes   # for renaming the subprocess

class App:

    myframe = None

    # variables for basic set-up
    nc = None
    nc_button = None
    myself = None
    direct_link = None
    direct_button = None
    frequency = None
    rate = None
    tx_gain = None
    rx_gain = None
    side = None
    
    # variables for relay control
    relay_frame = None
    timeout = 2
    
    # variables for node control
    node_id = None
    label_id = None
    A_button = None
    B_button = None
    node_frame = None
    file_source = None
    file_name_field = None
    file_name_button = None
    fixed_data = None
    
    # variables for displaying results
    frame_errors = None
    thoughput = None
    tx_num = None
    tx_data = None
    rx_num = None
    rx_data = None
    num_timeouts = None
    running = False
    timeout_entry = None
    timeout_label = None
    
    # variables for controlling the flow graph
    tb_tx = None
    tb_rx = None
    
    # variables for controlling the run state
    run_button = None
    cancel_button = None
    pid = None

    def __init__(self, master):

        master.title("GNU Radio Relaying")

        network_frame = Frame(master)
        network_frame.grid(sticky=NW)
        Label(network_frame, text="Network set-up:", font=("Times", "12", "bold underline")).grid(sticky=NW)
        frame = Frame(network_frame)
        self.myframe = frame
        frame.grid(column=0, row=1, sticky=NW)

        # Selection for enabling peer2peer, one way or two way communication
        self.dualway = IntVar()
        p2p = Radiobutton(frame, state=NORMAL, text="Point to point (Relay <-> A)", command=self.setValue, variable=self.dualway, value=0)
        p2p.grid(sticky=NW)
        Radiobutton(frame, state=NORMAL, text="One-way relaying (A -> B)", command=self.setValue, variable=self.dualway, value=1).grid(sticky=NW)
        Radiobutton(frame, state=NORMAL, text="Two-way relaying (A <-> B)", command=self.setValue, variable=self.dualway, value=2).grid(sticky=NW)

        # Checkbox for enabling network coding
        self.nc = IntVar()
        self.nc_button = Checkbutton(frame, state=NORMAL, text="Network Coding", variable=self.nc)
        self.nc_button.grid(sticky=NW)

        # Checkbox for enabling usage of direct link
        self.direct_link = IntVar()
        self.direct_button = Checkbutton(frame, state=NORMAL, text="Direct link usage", variable=self.direct_link)
        self.direct_button.grid(sticky=NW)

        # list with different channel coding possiblities
        Label(frame, text="Channel Coding:").grid(sticky=NW)
        self.channel_code = IntVar()
        cc = Radiobutton(frame, state=NORMAL, text="No channel coding", command=self.setValue, variable=self.channel_code, value=0)
        cc.grid(sticky=NW)
        Radiobutton(frame, state=NORMAL, text="Reed-Solomon Code", command=self.setValue, variable=self.channel_code, value=1).grid(sticky=NW)

        #space
        space_frame = Frame(network_frame)
        space_frame.grid(column=1, row=1, sticky=NW)
        Label(space_frame, text="    ").grid()

        # one out of multiple selection of the type of the station
        type_frame_general = Frame(network_frame)
        type_frame_general.grid(column=2, row=1, sticky=NE)
        type_frame = Frame(type_frame_general)
        type_frame.grid()
        Label(type_frame, text="Role of this station in the network:").grid(sticky=NW)
        self.myself = IntVar()
        relay_button = Radiobutton(type_frame, text="Relais", variable=self.myself, value=0, command=self.type_selection)
        relay_button.grid(sticky=NW)
        node_button = Radiobutton(type_frame, text="Node", variable=self.myself, value=1, command=self.type_selection)
        node_button.grid(sticky=NW)

        # selection of the node-ID
        id_frame = Frame(type_frame_general)
        id_frame.grid(sticky=NW)
        self.label_id = Label(id_frame, text="Select an ID:")
        self.label_id.grid(sticky=NW)
        self.node_id = StringVar()
        self.A_button = Radiobutton(id_frame, text="A", variable=self.node_id, value='A')
        self.A_button.grid(sticky=NW)
        self.B_button = Radiobutton(id_frame, text="B", variable=self.node_id, value='B')
        self.B_button.grid(sticky=NW)
        
        # general parameters which must be equal for the hole network
        parameter_frame = Frame(network_frame)
        parameter_frame.grid(sticky=SW)
        
        # frequency
        Label(parameter_frame, text="Frequency: ").grid(sticky=NW)
        self.frequency=StringVar()
        Entry(parameter_frame, textvariable=self.frequency, width=5).grid(column=1, row=0, sticky=NW)
        self.frequency.set('5375M')
        # rate
        Label(parameter_frame,  text="Rate: ").grid(sticky=NW)
        self.rate = StringVar()
        Entry(parameter_frame, textvariable=self.rate, width=5).grid(column=1, row=1, sticky=NW)
        self.rate.set('1024k')        #512 is also possible

        # setting of general settings for this station
        settings_frame = Frame(master)
        settings_frame.grid(sticky=NW)
        Label(settings_frame, text="General settings of this station:", font=("Times", "12", "bold underline")).grid(sticky=NW)
        
        settings_frame_details = Frame(settings_frame)
        settings_frame_details.grid(row=1, sticky=NW)
        # tx-gain
        Label(settings_frame_details, text="TX-gain: ").grid(sticky=NW)
        self.tx_gain=StringVar()
        Entry(settings_frame_details, textvariable=self.tx_gain, width=3).grid(column=1, row=0, sticky=NW)
        self.tx_gain.set('20')
        # rx-gain
        Label(settings_frame_details,  text="RX-gain: ").grid(sticky=NW)
        self.rx_gain = StringVar()
        Entry(settings_frame_details, textvariable=self.rx_gain, width=3).grid(column=1, row=1, sticky=NW)
        self.rx_gain.set('46')
        
        add_settings_frame = Frame(master)
        add_settings_frame.grid(sticky=NW)
        # side
        self.side=StringVar()
        Label(add_settings_frame, text='Side of daughterboard:').grid(sticky=NW)
        db = Radiobutton(add_settings_frame, text='A', variable=self.side, value='A', state=NORMAL)
        db.grid(sticky=NW)
        Radiobutton(add_settings_frame, text='B', variable=self.side, value='B', state=NORMAL).grid(sticky=NW)
        db.invoke()
        
        # setting of relay settings
        self.relay_frame= Frame(master)
        self.relay_frame.grid(sticky=NW)
        Label(self.relay_frame, text="Relay settings:", font=("Times", "12", "bold underline")).grid(sticky=NW)
        # timeout:
        Label(self.relay_frame, text="Timeoutlimit (in s): ").grid(sticky=NW)
        self.timeout=IntVar()
        Entry(self.relay_frame, textvariable=self.timeout, width=4).grid(column=1, row=1, sticky=NW)
        self.timeout.set(2)    # give a default value

        # setting of node settings
        self.node_frame= Frame(master)
        self.node_frame.grid(sticky=NW)
        Label(self.node_frame, text="Node settings:", font=("Times", "12", "bold underline")).grid(sticky=NW)
        Label(self.node_frame, text="Burst size:").grid(sticky=NW)
        self.burst_size = IntVar()
        self.burst_size_field = Entry(self.node_frame, textvariable=self.burst_size, width=5)
        self.burst_size_field.grid(row=1,sticky=N)
        self.burst_size.set(1)
        Label(self.node_frame, text="Select data source:").grid(sticky=NW)
        self.type_transmission = StringVar()
        self.fixed_data = Radiobutton(self.node_frame, text="Fixed data (213 times a 5)", variable=self.type_transmission, value='C', command=self.source_select)
        self.fixed_data.grid(sticky=NW)
        Radiobutton(self.node_frame, text="File transfer", variable=self.type_transmission, value='F', command=self.source_select).grid(sticky=NW)
        self.file_source = StringVar()
        self.file_name_field = Entry(self.node_frame, textvariable=self.file_source, width=25)
        self.file_name_field.grid(column=0, row=5, sticky=NW)
        self.file_name_button = Button(self.node_frame, text="Select", command=self.select_file)
        self.file_name_button.grid(column=1, row=5, sticky=NW)
        Radiobutton(self.node_frame, text="Video transfer", variable=self.type_transmission, value='V', command=self.source_select).grid(sticky=NW)
        Radiobutton(self.node_frame, text="Random data (from /dev/urandom)", variable=self.type_transmission, value='R', command=self.source_select).grid(sticky=NW)

        # space
        space_frame = Frame(master)
        space_frame.grid(column=3)
        Label(space_frame, text="    ").grid()

        # part of the window to display measurement results
        result_frame = Frame(master)
        result_frame.grid(column=4, row = 0, sticky=NW)
        Label(result_frame, text="Measurement Results:", font=("Times", "12", "bold underline")).grid(row=0, sticky=NW)
        result_frame_details = Frame(result_frame)
        result_frame_details.grid(row=1, sticky=NW)
        # frame error rate
        Label(result_frame_details, text="Acutal frame error rate (in %): ").grid(sticky=NW)
        self.frame_errors = IntVar()
        Entry(result_frame_details, textvariable=self.frame_errors, width=10).grid(column=1, row=0, sticky=NW)
        # throughput
        Label(result_frame_details, text="Actual throughput (bit / second): ").grid(sticky=NW)
        self.throughput = IntVar()
        Entry(result_frame_details, textvariable=self.throughput, width=10).grid(column=1, row=1, sticky=NW)
        # empty line
        Label(result_frame_details,  text="  ").grid(row=2, sticky=NW)
        # transmitted packets
        Label(result_frame_details, text="Number of transmitted packets: ").grid(sticky=NW)
        self.tx_num = StringVar()
        Entry(result_frame_details, textvariable=self.tx_num, width=10).grid(column=1, row=3, sticky=NW)
        self.tx_num.set("0")
        Label(result_frame_details, text="Amount of transmitted data (byte): ").grid(sticky=NW)
        self.tx_data = StringVar()
        Entry(result_frame_details, textvariable=self.tx_data, width=10).grid(column=1, row=4, sticky=NW)
        self.tx_data.set("0")

        # empty line
        Label(result_frame_details,  text="  ").grid(row=5, sticky=NW)
        
        # received packets
        Label(result_frame_details, text="Number of received packets: ").grid(sticky=NW)
        self.rx_num = StringVar()
        Entry(result_frame_details, textvariable=self.rx_num, width=10).grid(column=1, row=6, sticky=NW)
        self.rx_num.set("0")
        Label(result_frame_details, text="Amount of received data (byte): ").grid(sticky=NW)
        self.rx_data = StringVar()
        Entry(result_frame_details, textvariable=self.rx_data, width=10).grid(column=1, row=7, sticky=NW)
        self.rx_data.set("0")
        
        # empty line
        Label(result_frame_details,  text="  ").grid(row=8, sticky=NW)
        
        # number of occured timeouts, only for relay
        self.timeout_label = Label(result_frame_details, text="Number of occured timeouts: ")
        self.timeout_label.grid(sticky=NW)
        self.num_timeouts = StringVar()
        self.timeout_entry = Entry(result_frame_details, textvariable=self.num_timeouts, width=10)
        self.timeout_entry.grid(column=1, row=9, sticky=NW)
        self.num_timeouts.set("0")

        # bottom part of the window
        lower_frame = Frame(master)
        lower_frame.grid(column=4, sticky=SE)
        
        # buttons for starting, stopping gnuradio and quitting the hole program
        self.run_button = Button(lower_frame, text="Run", command=self.runstate)
        self.run_button.grid(column=0)
        self.cancel_button = Button(lower_frame, text="Cancel", command=self.stop, state = DISABLED)
        self.cancel_button.grid(column=1, row=0)
        Button(lower_frame, text="QUIT", fg="red", command=frame.quit).grid(column=2, row=0, sticky=SE)
        
        p2p.invoke()
        cc.invoke()
        self.A_button.invoke()
        node_button.invoke()
        relay_button.invoke()
        
        signal.signal(signal.SIGALRM, self.timeout_handler)
        
        libc = ctypes.CDLL("libc.so.6")
        libc.prctl(15, 'relaying\x00', 0, 0, 0)

    def type_selection(self):
        if self.myself.get() == 0:
            self.label_id["state"]=DISABLED
            self.A_button["state"]=DISABLED
            self.B_button["state"]=DISABLED
            # disable the frame with the node settings
            for child in self.node_frame.winfo_children():
                child["state"]=DISABLED
            # enable the frame with the relay settings
            for child in self.relay_frame.winfo_children():
                child["state"]=NORMAL
            self.direct_button["state"] = DISABLED
            self.timeout_label["state"] = NORMAL
            self.timeout_entry["state"] = NORMAL
        else:
            self.label_id["state"]=NORMAL
            self.A_button["state"]=NORMAL
            self.B_button["state"]=NORMAL
            # enable the frame with the node settings
            for child in self.node_frame.winfo_children():
                child["state"]=NORMAL
            self.fixed_data.invoke()
            # disable the frame with the relay settings
            for child in self.relay_frame.winfo_children():
                child["state"]=DISABLED
            if (self.dualway.get() != 0):
                self.direct_button["state"] = NORMAL
            self.timeout_label["state"] = DISABLED
            self.timeout_entry["state"] = DISABLED            

    def select_file(self):
        myPath = askopenfilename(filetypes=[("all formats", "*")])
        self.file_source.set(myPath)

    def source_select(self):
        if self.type_transmission.get() == 'F':   # only when file transfer is selected
            self.file_name_field["state"]=NORMAL
            self.file_name_button["state"]=NORMAL
        else:
            self.file_name_field["state"]=DISABLED
            self.file_name_button["state"]=DISABLED

    def runstate(self):
        if self.running == True:
            print "Already running!"
        else:
            self.running = True
            self.run_button["state"] = DISABLED
            self.cancel_button["state"] = NORMAL
            #reset all statistics
            self.frame_errors.set(str(0))
            self.throughput.set(str(0))    # bit / second
            self.tx_num.set(str(0))
            self.tx_data.set(str(0))  # in byte
            self.rx_num.set(str(0))
            self.rx_data.set(str(0))  # in byte
            self.num_timeouts.set(str(0))
                
            if self.myself.get() == 0:
                relay = True
            else:
                relay = False
            if (self.dualway.get() == 0) or (self.dualway.get() == 1):
                bidirectional = False
            else:
                bidirectional = True
            if self.dualway.get() == 0:
                benchmark = True
            else:
                benchmark = False
            timeout = self.timeout.get()
            burst = self.burst_size.get()
            if self.nc.get() == 0:
                nc = False
            else:
                nc = True
            if self.direct_link.get() == 0:
                direct_link = False
            else:
                direct_link = True
            try:
                if (self.type_transmission.get() == 'V') and (self.node_id.get() == 'B'):
                    self.video = True
                else:
                    self.video = False
                self.read, self.write = os.pipe() # these are file descriptors, not file objects
                self.pid = os.fork()
                if self.pid != 0:    # parent
                    signal.signal(signal.SIGCONT, self.update_statistic)
                else:           # child
                    self.myframe.quit()
                    libc = ctypes.CDLL("libc.so.6")
                    libc.prctl(15, 'GNURadio\x00', 0, 0, 0)
                    main(relay, self.side.get(), self.frequency.get(), self.rate.get(), self.tx_gain.get(), self.rx_gain.get(), self.type_transmission.get(), nc, direct_link, bidirectional, benchmark, self, self.write, timeout, self.node_id.get(), burst, self.channel_code.get())
            except:
                print "Stopped due to exception!"
                pass        # stopped due to user interaction or due to timeout
        
    def stop(self):
        if self.running == True:
            print "Stopping the running gnuradio."
            signal.alarm(0)
            signal.alarm(5)     # start timeout, the following commands have 5 s to complete
            os.kill(self.pid, signal.SIGTERM)
            if self.video == True:
                Popen(["killall", "-9", "vlc"])   # shut down VLC
            try:
                os.waitpid(self.pid, 0) # there will be a last update of the gui which will interrupt this
            except:
                pass
            self.running = False
            self.cancel_button["state"] = DISABLED
            self.run_button["state"] = NORMAL   # it is assumed that gnuradio can be started again
        else:
            print "Nothing to stop!"
        signal.alarm(0)
            
    def timeout_handler(self, signum, frame):
        Popen(["killall", "-9", "GNURadio"])  # killing gnuradio as it did not terminate normally
        
    def setValue(self):
        if (self.dualway.get() == 0):
            self.nc_button["state"]=DISABLED
            self.nc.set(False)
            self.direct_button["state"]=DISABLED
            self.direct_link.set(False)
        elif (self.dualway.get() == 1):
            self.nc_button["state"]=DISABLED
            self.nc.set(False)
            if self.myself.get() != 0:
                self.direct_button["state"]=NORMAL
        else:
            self.nc_button["state"]=NORMAL
            if self.myself.get() != 0:
                self.direct_button["state"]=NORMAL
            
    def update_statistic(self, signum, frame):
        try:
            update = os.read(self.read, 100)    # read the update information from the pipe
        except:
            print "update failed"
        #print "I read from pipe nr. " + str(self.read)
        content = re.match(r"(\w+) (\w+) (\w+) (\w+\.\w+) (\w+) (\w+) (\w+)", update)    # 7 parts
        if content is not None:
            #print "updated my statistic!"
            self.update_statistic_direct(int(content.group(1)), int(content.group(2)), int(content.group(3)), float(content.group(4)), int(content.group(5)), int(content.group(6)), int(content.group(7)))
        else:
            print str(update)
            print "update failed"
            
    # function to update the display statistical information inside the GUI
    def update_statistic_direct(self, rx_num, rx_right, tx_num, elapsed_time, rx_data, tx_data, timeouts = 0):
        #error rate
        if (rx_num is not 0) or (tx_num is not 0):  # only if any packet has been sent or received
            if rx_num != 0:
                self.frame_errors.set(str((rx_num - rx_right + 0.0) / rx_num * 100))  # in percent
            #throughput
            self.throughput.set(str((rx_data + 0.0)*8/elapsed_time))    # bit / second
            self.tx_num.set(tx_num)
            self.tx_data.set(str(tx_data))  # in byte
            self.rx_num.set(rx_num)
            self.rx_data.set(str(rx_data))  # in byte
            #timeouts
            if self.myself.get() == 0:   # only the relay has a timeout
                self.num_timeouts.set(str(timeouts))
        else:   # data in pipe consits only of zeros, nothing to do
            pass

root = Tk()

app = App(root)

root.mainloop()

sys.exit()
