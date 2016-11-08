FROM_NET >> (in) CheckHeader@NIC

// get request
CheckHeader (get) >> GetRequest@NIC (queue_insert) >> (put) SteeringQueue (get) <> app_loop@APP_CORE >> (lookup) KVS@APP_CORE (add_queue) >> (in) OutQueue (get_resp) >> GetResponse@NIC >> TO_NET;
(lookup) KVS@APP_CORE (add_value) >> ValueBuffer (get) <> (get_value) GetResponse@NIC;

// set request
CheckHeader (set) >> (insert) LogManager@NIC >> (put) SteeringQueue (get) <> app_loop@APP_CORE >> (store) KVS@APP_CORE >> (in) OutQueue (get_resp) >> SetResponse@NIC >> TO_NET;
app_loop@APP_CORE >> (full) LogManager@APP_CORE (add_queue) >> (in) OutQueue >> (new_seg) LogManager@NIC;

// unknown
CheckHeader (except) >> Exception@NIC;

Component CheckHeader@NIC {
  requires void get(packet p, uint32_t key_hash, uint6_t core_id);
  requires void set(packet p, uint32_t key_hash, uint6_t core_id);
  requires void except(packet p, uint32_t key_hash);
  provides void in(packet p) {
    uint1_t pass = 1;
    // check header
    // if fail, set pass = 0 

    if(pass) {
      uint32_t key_hash = hash(CRC, p.key);
      uint6_t core_id = reta[eqe.key_hash & 0xff]; 
      if(p.opcode == OP_GET) get(p, key_hash, core_id);
      else set(p, key_hash, core_id);
    } else { except(p); }
  }
}

///////////////////// get @NIC ///////////////////////
Component GetRequest@NIC {
  requires void queue_insert(eqe_entry p, uint16_t size);
  provides void get(packet p, uint32_t key_hash, uint6_t core_id) {
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

///////////////////// set @NIC ///////////////////////
struct lseg {
  int base, len, pos;
}

struct log_region {
  int active_seg = 0;
  lseg segments[M];
}

Component LogManager@NIC {
  log_region regions[N];

 Channel {
  requires void queue_insert(eqe_entry p, uint16_t size);
  require void write_DMA(size_t addr, size_t size, entry val);

  provides void insert(packet p, uint32_t key_hash, uint6_t core_id) {
    log_region region = regions[core_id];
    int addr = item_allocation(region, p.keylen + p.vallen);
    item i;
    // ...
    call DMAWrite(addr, sizeof(item + p.keylen + p.vallen), i); // call
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
  provides void new_seg(int index, lseg seg) { regions[index] = seg; }
 }
}

///////////////////// Descriptor Queue ///////////////////////
Composite SteeringQueue {
  provides void put(eqe_entry p, size_t size, uint6_t core_id);
  provides eqe_entry get();

  Implementation {
    (this.put) == (enqueueRx) NICQueue@NIC (write_DMA) >> (write) DMAWrite (read) <> (read) APPQueue@APP_CORE (dequeueRx) == (this.get);
  }
}


struct queue {
  uint32_t start, end, head, tail;
}


Component DMAWrite {
  provides void write(size_t addr, size_t size, entry val); // @NIC
  provides entry read(size_t addr); // @APP_CORE, should this return an struct instance or a pointer?
}

Component NICQueue@NIC {
  queue cores_rx[N];

  Channel {
    require void write_DMA(size_t addr, size_t size, entry val);
    provides void enqueueRX(eqe_entry p, size_t size, uint6_t core_id) {
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
