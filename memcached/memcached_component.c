/**********************************************************************/
/* Receiving */

FROM_NET >> (in) ExtractKey@NIC (queue_insert) >> (put) SteeringQueue (get) <> get_request@API; // API**
ExtractKey@NIC (slow) >> (in) SlowPath;

Component ExtractKey@NIC {
  requires void queue_insert(eqe_entry p, uint16_t size);
  requires void slow(packet p);
  provides void in(packet p) {
    uint32_t key_hash = hash(CRC, p.key);

    uint1_t pass = 1;
    // check header
    // if fail, set pass = 0 and call slow()

    if(pass) {
      if(p.opcode = OP_GET) {
        eqe_rx_get eqe; // do we have to worry about stack dellocation after return?
        eqe = cast<eqe_rx_get>(p); // copy common fields
        //eqe.src_port = p.src_port; 
        //eqe.src_ip   = p.src_ip;
        //eqe.key = p.key;
        eqe.type = EQE_TYPE_GET;
        eqe.hash = key_hash;
        eqe.keylen = p.keylen;
        uint16_t len = sizeof(eqe) + p.keylen;
        post queue_insert(eqe, len);
      } else {
        log_seg_r lseg = log_segs[log_seg_cur];
        eqe_rx_set eqe;
        //???
        log_insert(...);
        post queue_insert(eqe);
      }
    } // end pass

  }
}

Composite SteeringQueue {
  provides void put(eqe_entry p, size_t size);
  provides eqe_entry get();

  Implementation {
    (this.put) == (enqueueRx) NICQueue@NIC (write_DMA) >> (write) DMAWrite (read) <> (read) APPQueue@APP_CORE (dequeueRx) == (this.get);
  }
}

struct core_r {
  uint32_t start, end, head, tail;
}

Component DMAWrite {
  provides void write(size_t addr, size_t size, entry val); // @NIC
  provides entry read(size_t addr); // @APP_CORE, should this return an struct instance or a pointer?
}

Component NICQueue@NIC {
  core_r cores_rx[N];

  Channel {
    require void write_DMA(size_t addr, size_t size, entry val);
    provides void enqueueRX(eqe_entry p, size_t size) {
      uint6_t core_id = reta[eqe.key_hash & 0xff]; 
      core_r core = cores_rx[core_id];
    
      if(core's queue is not full) {
        post write_DMA(core.head, size, eqe); // pointer
        // core.tail = ;
      }
      else { /* drop?? */ }
    }
  }

  Channel {
    require void out(packet_out p);
    require entry read(size_t addr);
    provides void dequeueTX(doorbell db) { 
      ...
      if(db.rx_head != -1)
        cores_rx[db.core_id].head = db.rx_head;
      entry e = read(db.addr);
      post out(e);
    }
  }
}

Component APPQueue@APP_CORE {
  core_r core;


  Channel {
    requires entry read(size_t addr);
    provides eqe_entry dequeueRX() {
      eqe_entry e =  read(core.head);
      if(e.owner_bit) {
        e.owner_bit = 0;
        // core.head = ;
        return e;
      } else { return null; }
    }
  }

  Channel {
    provides void enqueueTX(entry e);
  }
}
