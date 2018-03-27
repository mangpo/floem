
        if(rdtsc() >= dccp->retrans_timeout) {
            dccp->connections[worker].pipe = 0;
            __sync_fetch_and_add(&dccp->link_rtt, dccp->link_rtt);
        }
        if(dccp->connections[worker].pipe >= dccp->connections[worker].cwnd) {
            worker = -1;
        }

        (void* p, int worker) = inp();
        struct pkt_dccp_headers* header = p;
        rte_spinlock_lock(&dccp->global_lock);
        dccp->retrans_timeout = rdtsc() + dccp->link_rtt * PROC_FREQ_MHZ;
        dccp->link_rtt = LINK_RTT;
        uint32_t seq = __sync_fetch_and_add(&dccp->connections[worker].seq, 1);
        header->dccp.seq_high = seq >> 16;
        header->dccp.seq_low = htons(seq & 0xffff);
#ifdef DEBUG_DCCP
        //printf("Send to worker %d: seq = %x, seq_high = %x, seq_low = %x\n", worker, seq, header->dccp.seq_high, header->dccp.seq_low);
#endif
        rte_spinlock_unlock(&dccp->global_lock);

        __sync_fetch_and_add(&dccp->connections[worker].pipe, 1);

        (struct pkt_dccp_ack_headers* ack, struct pkt_dccp_headers* p) = inp();
        memcpy(ack, &dccp->header, sizeof(struct pkt_dccp_headers));
        ack->eth.dest = p->eth.src;
        ack->eth.src = p->eth.dest;
        ack->ip.dest = p->ip.src;
        ack->ip.src = p->ip.dest;
        ack->dccp.hdr.src = p->dccp.dst;
        ack->dccp.hdr.res_type_x = DCCP_TYPE_ACK << 1;
        uint32_t seq = (p->dccp.seq_high << 16) | ntohs(p->dccp.seq_low);
        ack->dccp.ack = htonl(seq);
        ack->dccp.hdr.data_offset = 4;

        dccp->acks_sent++;
        __sync_synchronize();


    // Wraparound?
	if((int32_t)ntohl(ack->dccp.ack) < connections[srcworker].lastack &&
	   connections[srcworker].lastack - (int32_t)ntohl(ack->dccp.ack) > connections[srcworker].pipe &&
	   connections[srcworker].lastack > (1 << 23)) {
	  connections[srcworker].lastack = -((1 << 24) - connections[srcworker].lastack);
	}

	if(connections[srcworker].lastack < (int32_t)ntohl(ack->dccp.ack)) {
	  int32_t oldpipe = __sync_sub_and_fetch(&connections[srcworker].pipe,
						 (int)ntohl(ack->dccp.ack) - connections[srcworker].lastack);
	  if(oldpipe < 0) {
	    connections[srcworker].pipe = 0;
	  }

	  // Reset RTO
	  dccp->retrans_timeout = rdtsc() + dccp->link_rtt * PROC_FREQ_MHZ;
	  dccp->link_rtt = LINK_RTT;
	}

	if((int32_t)ntohl(ack->dccp.ack) > connections[srcworker].lastack + 1) {
#ifdef DEBUG_DCCP
	  printf("Congestion event for %d! ack %u, lastack + 1 = %u\n",
	 	 srcworker, ntohl(ack->dccp.ack),
	 	 connections[srcworker].lastack + 1);
#endif
	  // Congestion event! Shrink congestion window
	  uint32_t oldcwnd = connections[srcworker].cwnd, newcwnd;
	  do {
	    newcwnd = oldcwnd;
	    if(oldcwnd >= 2) {
	      newcwnd = __sync_val_compare_and_swap(&connections[srcworker].cwnd, oldcwnd, oldcwnd / 2);
	    } else {
	      break;
	    }
	  } while(oldcwnd != newcwnd);
	} else {
#ifdef DEBUG_DCCP
	  printf("Increasing congestion window for %d\n", srcworker);
#endif
	  // Increase congestion window
	  /* __sync_fetch_and_add(&connections[srcworker].cwnd, 1); */
	  connections[srcworker].cwnd++;
	}

	connections[srcworker].lastack = MAX(connections[srcworker].lastack, (int32_t)ntohl(ack->dccp.ack));
	connections[srcworker].acks++;
	output { out(p); }

        struct pkt_dccp_headers* header = p;
        state.tx_net_buf = b;
        struct tuple* t = state.q_buf.entry;
        memcpy(header, &dccp->header, sizeof(struct pkt_dccp_headers));
        struct tuple* new_t = &header[1];
        memcpy(new_t, t, sizeof(struct tuple));
        new_t->task = t->task;

        struct worker* workers = get_workers();
        header->dccp.dst = htons(state.worker);
        header->dccp.src = htons(state.myworker);
        header->eth.dest = workers[state.worker].mac;
        header->ip.dest = workers[state.worker].ip;
        header->eth.src = workers[state.myworker].mac;
        header->ip.src = workers[state.myworker].ip;
