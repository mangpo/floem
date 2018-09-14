int main() {}
        (size_t size, void* hdr, void* b) = inp();
        struct pkt_dccp_headers* p = hdr;
        int type = 0;
        if (ntohs(p->eth.type) == ETHTYPE_IP && p->ip._proto == IP_PROTO_DCCP) {
            if(((p->dccp.res_type_x >> 1) & 15) == DCCP_TYPE_ACK) type = 1;
            else type = 2;
            state.rx_pkt = p;
            state.rx_net_buf = b;
        }

        output switch {
            case type==1: ack(p);
            case type==2: pkt(p);
            else: drop();
        }

        (size_t size, void* p, void* b) = inp();
        state.rx_pkt = p;
        state.rx_net_buf = b;
        output { out(p); }

    struct tuple* t = inp();
        int id = this->task2executorid[t->task];
#ifdef DEBUG_MP
    printf("steer: task %d, id %d\n", t->task, id);
#endif
    output { out(t, id); }

    (struct tuple* t) = inp();
    bool local = (state.worker == state.myworker);

#ifdef DEBUG_MP
        if(local) printf("Local -- task = %d, fromtask = %d, local = %d\n", t->task, t->fromtask, local);
#endif

    output switch { case local: out_local(t); else: out_send(t); }

    (struct tuple* t) = inp();

        
    output switch { case t: out(t); }

        output { out(dccp); }

        (int worker) = inp();

        if(rdtsc() >= dccp->retrans_timeout) {
            dccp->connections[worker].pipe = 0;
            __sync_fetch_and_add(&dccp->link_rtt, dccp->link_rtt);
        }
        if(dccp->connections[worker].pipe >= dccp->connections[worker].cwnd) {
            worker = -1;
        }

        output switch { case (worker >= 0): send(worker); else: drop(); }

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
        output { out(p); }

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

        output { out(ack); }

        (struct pkt_dccp_headers* p) = inp();
        struct pkt_dccp_ack_headers *ack = (void *)p;
        int srcworker = ntohs(p->dccp.src);
        assert(srcworker < MAX_WORKERS);
        assert(ntohl(ack->dccp.ack) < (1 << 24));

        struct connection* connections = dccp->connections;
        //printf("Ack\n");

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

        struct tuple *t = inp();
        if(t) __sync_fetch_and_add(&dccp->tuples, 1);
        output { out(t); }

        void *t = inp();
        if(t) __sync_fetch_and_add(&dccp->tuples, 1);
        output { out(t); }

        (struct tuple* t) = inp();
        state.worker = this->task2worker[t->task];
        state.myworker = this->task2worker[t->fromtask];
        output { out(t); }

        output { out(state.worker); }

        (void* p) = inp();
        output { out(p, state.worker); }

        (size_t size, void* p, void* b) = inp();
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
        
        if(new_t->task == 30) printf("PREPARE PKT: task = %d, fromtask = %d, worker = %d\n", new_t->task, new_t->fromtask, state.worker);
        output { out(p); }

        (struct pkt_dccp_headers* p) = inp();
        struct tuple* t = (struct tuple*) &p[1];
        __sync_fetch_and_add(&dccp->tuples, 1);
        if(t->task == 30) printf("\nReceive pkt 30: %s, count %d!!!!!\n", t->v[0].str, t->v[0].integer);
        output { out(t); }

        output { out(%s); }

        (size_t size, void* tx_pkt, void* tx_buf) = inp();
        state.tx_net_buf = tx_buf;
        void* rx_pkt = state.rx_pkt;
        output { out(tx_pkt, rx_pkt); }

        (void* p) = inp();
        void* net_buf = state.tx_net_buf;
        output { out(%s, p, net_buf); }

        void* pkt = state.rx_pkt;
        void* pkt_buf = state.rx_net_buf;
        output { out(pkt, pkt_buf); }

    (int core_id) = inp();          
    int n_cores = %d;
    static __thread int core = -1;                                                                  
    static __thread int batch_size = 0;                                                            
    static __thread size_t start = 0; 

    if(core == -1) {
        //core = (core_id * n_cores)/%d;
        core = core_id;
        while(this->executors[core].execute == NULL)
            core = (core + 1) %s n_cores;               
        start = rdtsc();                                     
    }                                                             
                                                                       
    if(core >= 2 && (batch_size >= BATCH_SIZE || rdtsc() - start >= BATCH_DELAY)) {    
        int old = core;                                  
        do {                                                                      
            core = (core + 1) %s n_cores;                              
        } while(this->executors[core].execute == NULL);                 
        //if(old <=3 && core > 3) core = 2;             
        //if(old >=4 && core < 4) core = 4;             
        if(old >=2 && core < 2) core = 2;             
        //if(old >=1 && core < 1) core = 1;             
        batch_size = 0;                                        
        start = rdtsc();                                             
    }                                                             
    batch_size++;                                          
    output { out(core); }

    (struct tuple* t, uintptr_t addr) = inp();
    output { out(t); }

    (struct tuple* t) = inp();
    output { out(t, 0); }

    (q_buffer buff) = inp();
    struct tuple* t = buff.entry;
    if(t) t->starttime = rdtsc();
    state.q_buf = buff;
    output { out((struct tuple*) buff.entry); }

    q_buffer buff = state.q_buf;
    output { out(buff); }

    output { out(); }
