/**********************************************************************/
/* Receiving */


ExtractKey extract_key;
SteeringQueue steering_queue;
APPRecv app_recv;

FROM_NET >> (in) ExtractKey@NIC (queue_insert) >> (put) SteeringQueue (get) <> (get) APPRecv@APP_CORE; // API**
ExtractKey@NIC (slow) >> (in) SlowPath;

Element ExtractKey@NIC {
  requires void queue_insert(eqe_entry p, uint16_t size);
  requires void slow(packet p);
  provides void in(packet p) {
    uint32_t key_hash = hash(CRC, p.key);

    // check header
    uint1_t pass = 1;
    // if fail, set pass = 0 and call slow()

    if(pass) {
      if(p.opcode = OP_GET) {
        eqe_rx_get eqe;
        eqe = cast<eqe_rx_get>(p); // copy common fields
        //eqe.src_port = p.src_port; 
        //eqe.src_ip   = p.src_ip;
        //eqe.key = p.key;
        eqe.type = EQE_TYPE_GET;
        eqe.hash = key_hash;
        eqe.keylen = p.keylen;
        uint16_t len = sizeof(eqe) + p.keylen;
        queue_insert(eqe, len);
      } else {
        log_seg_r lseg = log_segs[log_seg_cur];
        eqe_rx_set eqe;
        //???
        log_insert(...);
        queue_insert(eqe);
      }
    } // end pass

  }
}

Composite SteeringQueue {
  provides void put(eqe_entry p, size_t size);
  provides eqe_entry get();

  Implementation {
    (this.put) == (put) EnqueueRx@NIC (write_DMA) >> (write) DMAWrite (read) <> (read) DequeueRx@APP_CORE (get) == (this.get);
  }
}

struct core_r {
  uint32_t start, end, head, tail;
}

Element EnqueueRx@NIC {
  core_r cores[N];

  require void write_DMA(size_t addr, size_t size, size_t* val);
  provides void put(eqe_entry p, size_t size) {
    uint6_t core_id = reta[eqe.key_hash & 0xff]; 
    core_r core = cores[core_id];
    
    if(core's queue is not full) {
      write_DMA(core.head, size, (size_t *) &eqe); // pointer
    }
    else { /* drop?? */ }
  }
}

Element DequeueRx@APP_CORE {
  requires ?? read(size_t addr); // TODO
  provides eqe_entry get() {

  }
}
