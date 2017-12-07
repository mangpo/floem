FROM_NET >> (in) CheckHeader@NIC

// get request
CheckHeader (get) >> (rx) GetRequest@NIC (to_cpu) >> (put) SteeringQueue (get) 
  <> app_loop@APP_CORE >> (lookup) KVS@APP_CORE (add_queue) >> (in) OutQueue 
  >> classify >> (tx) GetRequest@NIC (to_net) >> TO_NET;
(tx) GetRequest@NIC (DMA_read) >< (read) DMARead;

// set request
CheckHeader (set) >> (rx) SetRequest@NIC (to_cpu) >> (put) SteeringQueue (get) 
  <> app_loop@APP_CORE >> (store) KVS@APP_CORE (add_queue) >> (in) OutQueue 
  >> classify >> (tx) SetRequest@NIC (to_net) >> TO_NET;
(rx) SetRequest@NIC (DMA_write) >< (write) DMAWrite; // not very nice

// full segment
(rx) SetRequest@NIC (to_cpu) >> (put) SteeringQueue (get) 
  <> app_loop@APP_CORE >> (full) LogManager@APP_CORE (add_queue) >> (in) OutQueue 
  >> classify >> (new_seg) SetRequest@NIC;

// unknown
(in) CheckHeader@NIC (error) >> SlowPath@NIC;
(in) Classify@NIC (error) >> Exception@NIC >> TO_NET;

// API
process@API >> (run) app_loop@APP_CORE; // What is the semantics of >> (run)?
garbage_collec@API >> (collect) LogManager@APP_CORE;
// When using @API, programmers bind the computation units to the provided thread. For single-thread configuration, when @API connects to @APP_CORE, all called and posted actions @APP_CORE will be executed on that thread. The API call then returns when all computations are executed.
// For multi-thread configuration, the API call returns whenever the main thread has no more work to do. Essentially, it only guarantees to finish the entry action. 


Component CheckHeader@NIC {
  requires void get(packet p, uint32_t key_hash, uint6_t core_id);
  requires void set(packet p, uint32_t key_hash, uint6_t core_id);
  requires void error(packet p, uint32_t key_hash);
  provides void in(packet p) {
    uint1_t pass = 1;
    // check header
    // if fail, set pass = 0 

    if(pass) {
      uint32_t key_hash = hash(CRC, p.key);
      uint6_t core_id = reta[eqe.key_hash & 0xff]; 
      if(p.opcode == OP_GET) get(p, key_hash, core_id);
      else set(p, key_hash, core_id);
    } else { error(p); }
  }
}

Component Classify@NIC {
  
  requires void get(cqe_entry e);
  requires void set(cqe_entry e);
  requires void new_weg(cqe_entry e);
  requires void error(cqe_entry e);
  provides void in(cqe_entry e) {
    switch(e.type) {
      case CQE_TYPE_GET: post get(e); break;
      case CQE_TYPE_SET: post store(e); break;
      case CQE_SEG_REGISTER: post new_seg(e); break;
      case CQE_TYPE_ERROR: post error(e); break;
    }
  }
}

///////////////////// get @NIC ///////////////////////
Component GetRequest@NIC {
  Channel {
  requires void to_cpu(eqe_entry p, uint16_t size);
  provides void rx(packet p, uint32_t key_hash, uint6_t core_id) {
        eqe_rx_get eqe; // do we have to worry about stack dellocation after return?
        eqe = cast<eqe_rx_get>(p); // copy common fields
        //eqe.src_port = p.src_port; 
        //eqe.src_ip   = p.src_ip;
        //eqe.key = p.key;
        eqe.type = EQE_TYPE_GET;
        eqe.hash = key_hash;
        eqe.keylen = p.keylen;
        uint16_t len = sizeof(eqe) + p.keylen;
        post queue_insert(eqe, len, core_id);
  }
  }
  
  Channel {
    requires void to_net(packet_out p);
    provides void tx(cqe_entry e) {
      packet_out p = format_GET_response(call DMA_read(e.i, e.i_len), e.client); // TODO
      post to_net(p);
    }
  }
}

///////////////////// set @NIC ///////////////////////
struct lseg {
  int base, len, pos;
}

struct log_region {
  int active_seg = 0;
  lseg segments[M];
}

Component SetRequest@NIC {
  log_region regions[N];

 Channel {
  requires void queue_insert(eqe_entry p, uint16_t size);
  require void DMA_write(size_t addr, size_t size, entry val);

  provides void rx(packet p, uint32_t key_hash, uint6_t core_id) {
    log_region region = regions[core_id];
    int addr = item_allocation(region, p.keylen + p.vallen);
    item i;
    // ...
    call DMA_write(addr, sizeof(item + p.keylen + p.vallen), i); // call
    eqe_rx_set eqe;
    eqe = cast<eqe_rx_get>(p);
    eqe.type = EQE_TYPE_GET;
    eqe.item = addr;
    uint16_t len = sizeof(eqe);
    post queue_insert(eqe, len, core_id); // post
  }
  
  int item_allocation(log_region region, int size) {
    int len = size + sizeof(item);
    lseg active = region.segments[active_seg];
    if(active.len - active.pos < len) {
      eqe_seg_full eqe;
      eqe.type = EQE_SEG_FULL;
      eqe.last = active_seg;
      uint16_t len = sizeof(eqe);
      post queue_insert(eqe, len, core_id); // post
    } else { active_seg = (active_seg + 1) % M; }

    int addr = active.base + active.pos;
    active.pos += len;
    return addr;
  }
 }
 
 Channel {
   requires void to_net(packet_out p);
   provides void tx(cqe_entry e) {
     packet_out p = format_SET_response(e.client) // TODO
     post to_net(p);
   }
 }


 Channel {
   provides void new_seg(cqe_entry e) {
     regions[e.index] = e.seg; 
   }
 }
}

///////////////////// Queue ///////////////////////
Composite SteeringQueue {
  provides void put(eqe_entry p, size_t size, uint6_t core_id);
  provides eqe_entry get();

  Implementation {
    (this.put) == (enqueueRx) NICQueue@NIC (write_DMA) >> (write) DMAWrite (read) <> (read) APPQueue@APP_CORE (dequeueRx) == (this.get);
  }
}

Composite OutQueue {
  provides void in(cqe_entry p, size_t size, uint6_t core_id);
  requires void out(cqe_entry e);
  
  Implementation {
    (this.in) == (enqueueTX) APPQueue@APP_CORE (doorbell_write) >> (in) Doorbell (out) >> (dequeueTX) NICQueue@NIC (out) == (this.out);
    (enqueueTX) APPQueue@APP_Core (mem_write) >< (write) DMARead (read) <> (DMA_read) NICQueue@NIC (dequeueTX);
  }
}


struct queue {
  uint32_t start, end, head, tail;
}


Component DMAWrite {
  provides void write(size_t addr, size_t size, entry val); // @NIC
  provides entry read(size_t addr); // @APP_CORE, should this return an struct instance or a pointer?
}

Component DMARead {
  provides void write(size_t addr, size_t size, entry val); // @APP_CORE
  provides entry read(size_t addr); // @NIC
}

Component NICQueue@NIC {
  queue cores_rx[N];

  Channel {
    require void write_DMA(size_t addr, size_t size, entry val);
    provides void enqueueRX(eqe_entry p, size_t size, uint6_t core_id) {
      core_r core = cores_rx[core_id];
    
      if(cores queue is not full) {
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
      entry e = call DMA_read(db.addr);
      post out(e);
    }
  }
}

Component APPQueue@APP_CORE {
  core_r core_rx, core_tx;

  Channel {
    requires entry read(size_t addr);
    provides eqe_entry dequeueRX() {
      eqe_entry e =  read(core_rx.start + core_rx.head);
      if(e.owner_bit) {
        e.owner_bit = 0;
        // core.head = ;
        return e;
      } else { return null; }
    }
  }

  Channel {
    requries void doorbell_write(doorbell bd);
    requires void mem_write(size_t addr, size_t size, entry val);
    provides void enqueueTX(entry e) {
      // adjust core.head
      call mem_write(core_tx.start + core_tx.head, ...);
      doorbell db;
      db.addr = core_tx.start + core_tx.head;
      db.rx_head = core.rx_head;
      post doorbell_write(db);
    }
  }
}

///////////////////// APP ///////////////////////
// <> app_loop@APP_CORE >> (lookup) KVS@APP_CORE (add_queue) >> (in) OutQueue (get_resp) >> GetResponse@NIC >> TO_NET;
// DMARead (read) <> (read) GetResponse@NIC;

Component app_loop@APP_CORE {
  requires eqe_entry get();
  requires void lookup(eqe_entry e);
  requires void store(eqe_entry e);
  requires void full(eqe_entry e);
  provides void run() {
    eqe_entry e = get();
    switch(e.type) {
      case EQE_TYPE_GET: post lookup(e); break;
      case EQE_TYPE_SET: post store(e); break;
      case EQE_FULL_SEG: post full(e); break;
    }
  }
}

Component KVS@APP_CORE {
  requires void add_queue(cqe_entry e);
  
  void add_GET_txqueue(item i, uint32_t client) {
    // e = create cqe_send_getresponse
    post add_queue(e);
  }
  
  void add_FAIL_txqueue(uint32_t client) {
    // e = create cqe_send_error
    post add_queue(e);
  }
  
  void add_SET_txqueue(uint32_t client) {
    // e = create cqe_send_setresponse
    post add_queue(e);
  }
  
  provides void lookup(eqe_entry e) {
    item i = hash_table_lookup(e.hash, e.key);
    if(i)
      add_GET_txqueue(i, e.client);
    else
      add_FAIL_txqueue(e.client);
  }
  
  provides void store(eqe_entry e) {
    hash_insert(e.hash, e.item)
    add_SET_txqueue(e.client)
  }

}

Component LogManager@APP_CORE {
  lseg unused_segments[L]; // per core
  
  // Register new log segment to NIC
  Channel {
    requires void add_queue(cqe_entry e);
  
    void add_SEG_REGISTER(lseg seg) {
      // e = create CQE_SEG_REGISTER
      post add_equeue(e);
    }
  
    provides void full(eqe_entry e) {
      gc_register_full_segment(e.base);
      add_SEG_REGISTER(get_unused_segment());
    }
  }
  
  // Garbage collcection
  Channel {
    void clear_segment(lseg) {
      for i in live_segments(lseg):
        move_to_new_segment(i)
      unused_segments += lseg
    }
    
    provides void collect() {
      for lseg in log segments with live items:
        stats = scan_segment(lseg)
        if stats.free / stats.total < THRESHOLD:
          clear_segment(lseg)
    }
  }
}


