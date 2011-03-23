/* -*- c++ -*- */
/*
 * Copyright 2005,2006 Free Software Foundation, Inc.
 * 
 * This file is part of GNU Radio
 * 
 * GNU Radio is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 3, or (at your option)
 * any later version.
 * 
 * GNU Radio is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with GNU Radio; see the file COPYING.  If not, write to
 * the Free Software Foundation, Inc., 51 Franklin Street,
 * Boston, MA 02110-1301, USA.
 */

#ifndef INCLUDED_FRAMER_SINK_RS_H
#define INCLUDED_FRAMER_SINK_RS_H

#include <gr_sync_block.h>
#include <gr_msg_queue.h>

class framer_sink_rs;
typedef boost::shared_ptr<framer_sink_rs> framer_sink_rs_sptr;

framer_sink_rs_sptr 
framer_make_sink_rs (gr_msg_queue_sptr target_queue);

/*!
 * \brief Given a stream of bits and access_code flags, assemble packets.
 * \ingroup sink_blk
 *
 * input: stream of bytes from gr_correlate_access_code_bb
 * output: none.  Pushes assembled packet into target queue
 *
 * The framer expects a fixed length header of 2 16-bit shorts
 * containing the payload length, followed by the payload.  If the 
 * 2 16-bit shorts are not identical, this packet is ignored.  Better
 * algs are welcome.
 *
 * The input data consists of bytes that have two bits used.
 * Bit 0, the LSB, contains the data bit.
 * Bit 1 if set, indicates that the corresponding bit is the
 * the first bit of the packet.  That is, this bit is the first
 * one after the access code.
 */
class framer_sink_rs : public gr_sync_block
{
  friend framer_sink_rs_sptr 
  framer_make_sink_rs (gr_msg_queue_sptr target_queue);

 private:
  enum state_t {STATE_SYNC_SEARCH, STATE_HAVE_SYNC, STATE_HAVE_HEADER};

  static const int MAX_PKT_LEN    = 4096;
  static const int HEADERBITLEN   = 32;

  gr_msg_queue_sptr  d_target_queue;		// where to send the packet when received
  state_t            d_state;
  unsigned int       d_header;			// header bits
  int		     d_headerbitlen_cnt;	// how many so far

  unsigned char      d_packet[MAX_PKT_LEN];	// assembled payload
  unsigned char	     d_packet_byte;		// byte being assembled
  int		     d_packet_byte_index;	// which bit of d_packet_byte we're working on
  int 		     d_packetlen;		// length of packet
  int                d_packet_whitener_offset;  // offset into whitener string to use
  int		     d_packetlen_cnt;		// how many so far

 protected:
  framer_sink_rs(gr_msg_queue_sptr target_queue);

  void enter_search();
  void enter_have_sync();
  void enter_have_header(int payload_len, int whitener_offset);
  
  unsigned int decode_header()
  {
    unsigned int i, weight = 0, ret = 0;
    for(i = 0; i < 12; i++)
      weight += (d_header >> i) & 0x1;	// calculate the hamming weight of the received header
    for(i = 16; i < 28; i++)            // do not count weightener offset, as our flow graph does not use this we do not care!
      weight += (d_header >> i) & 0x1;
    if (weight < 12)
      d_header = 5;
    else if (weight > 12)
      d_header = 260;
    else	// this means there is an equal amounts of 0s and 1s and therefore we could only guess
      ret = 1;  // signal an error
    return ret;
  }

  bool header_ok()
  {
    return decode_header() == 0;  //check if the decoder is able to make a decision
  }

  void header_payload(int *len, int *offset)
  {
    // header consists of two 16-bit shorts in network byte order
    // payload length is lower 12 bits
    // whitener offset is upper 4 bits
    *len = (int) d_header;
    *offset = (int) 0;
    //*offset = (d_header >> 28) & 0x000f;  //enable this if you want to use whitener offsets
  }

 public:
  ~framer_sink_rs();

  int work(int noutput_items,
	   gr_vector_const_void_star &input_items,
	   gr_vector_void_star &output_items);
};

#endif /* INCLUDED_FRAMER_SINK_RS_H */
