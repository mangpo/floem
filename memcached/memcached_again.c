FROM_NET >> CheckHeader@NIC

// get request
CheckHeader [get] >> GetRequest@NIC >> SteeringQueue [lookup] >> KVSLookup@APP_CORE >> OutQueue [get] >> GetResponse@NIC >> TO_NET;
AppEntry@APP_CORE >> SteeringQueue;

// set request
CheckHeader [set] >> SetRequest@NIC [forward] >> SteeringQueue [store] >> KVSStore@APP_CORE >> OutQueue [set] >> SetRequest@NIC >> TO_NET;

// full segment
SetRequest@NIC [full_segment] >> FullSegment@NIC >> SteeringQueue [full_segment] >> NewSegment@APP_CORE >> OutQueue [new_seg] >> RegisterSegment@NIC;

// unknown
CheckHeader@NIC [error] >> SlowPath@NIC;
Classify@NIC [error] >> Exception@NIC >> TO_NET;

// API
process@API >> [dequeue] SteeringQueue; 
// Do we have to make programmers explicity say what process executes? ... to part of OutQueue
// Is it enough to explain about thread of control and let them reason what is executed?
garbage_collec@API >> LogCollection@APP_CORE;
// When using @API, programmers bind the computation units to the provided thread. For single-thread configuration, when @API connects to @APP_CORE, all called and posted actions @APP_CORE will be executed on that thread. The API call then returns when all computations are executed.
// For multi-thread configuration, the API call returns whenever the main thread has no more work to do. Essentially, it only guarantees to finish the entry action. ???

struct queue {
  uint32_t base, len, head, tail;
}

State Queue@NIC {
  queue queues_rx[N];
  queue queues_tx[N];
}

// Multiple output ports
// If we connect one output port to multiple elements. All elements will get executed.
Element CheckHeader@NIC {
  input port in(packet);
  output port get(packet p, uint32_t key_hash, uint6_t core_id);
  output port set(packet p, uint32_t key_hash, uint6_t core_id);
  output port error(packet p, uint32_t key_hash);

  provides void in(packet p) {
    packet in = in();
    uint1_t pass = 1;
    // check header
    // if fail, set pass = 0 

    if(pass) {
      uint32_t key_hash = hash(CRC, p.key); // provided function hash
      uint6_t core_id = reta[eqe.key_hash & 0xff]; 
      if(p.opcode == OP_GET) get(p, key_hash, core_id);
      else set(p, key_hash, core_id);
    } else { error(p); }
  }
}

///////////////////// get @NIC ///////////////////////
Element GetRequest@NIC {
  input port in(packet p, uint32_t key_hash, uint6_t core_id);
  output port out(eqe_entry p, uint16_t size, uint6_t core_id);

  run {
    (packet p, uint32_t key_hash, uint6_t core_id) = in();
        eqe_rx_get eqe; // do we have to worry about stack dellocation after return?
        eqe = cast<eqe_rx_get>(p); // copy common fields
        //eqe.src_port = p.src_port; 
        //eqe.src_ip   = p.src_ip;
        //eqe.key = p.key;
        eqe.type = EQE_TYPE_GET;
        eqe.hash = key_hash;
        eqe.keylen = p.keylen;
        uint16_t len = sizeof(eqe) + p.keylen;
        out(eqe, len, core_id);
  }
}
  
// Much more productive
Element GetResponse@NIC {
    output port out(packet_out p);
    input port in(cqe_entry e);

    run {
      eqe_entry e = in();
      packet_out p = format_GET_response(DMA_read(e.i, e.i_len), e.client); // Use DMA like a function call
      out(p);
    }
}

//**** OR
Composite GetResponse@NIC {
    output port out(packet_out p);
    input port in(cqe_entry e);

  Implement {
    [in] >> GetResponseMain [dma_read] >> DMARead >> [value] FormatGetResponse >> [out];
    GetResponseMain [client] >> [client] FormatGetResponse;
  }
}

Element GetResponseMain@NIC {
  input port in(cqe_entry e);
  output port dma_read(size_t addr, size_t size);
  output port client(int client);

  Run {
    cqe_entry e = in();
    dma_read(e.i, e.i_len);
    client(e.client);
  }
}


// Multiple input ports = wait for all of them
// One input port with multiple input connections = wait for one of them
Element FormatGetResponse@NIC {
  input port value(?);
  input port client(int client);
  output port out(packet_out p);

  run {
    out(format_GET_response(value(), client()));
  }
}
//**** END OR

///////////////////// Queue ///////////////////////
Composite SteeringQueue {
  input port in(eqe_entry p, size_t size, uint6_t core_id);
  input port dequeue();
  output port lookup(eqe_get);
  output port store(eqe_set);
  output port full_segment(eqe_full_seg);

  Implementation {
    [in] >> NICSteeringQueue@NIC; [dequeue] >> APPSteeringQueue@APP_CORE >> Classify@APP_CORE >> [lookup,store,full_segment]; // automatically connect matching-name ports
  }
}


Composite OutQueue {
  input port in(cqe_entry p, size_t size);
  output port get(cqe_get);
  output port set(cqe_set);
  output port new_seg(cqe_reigster_seg);

  Implementation {
    [in] >> APPOutQueue@APP_CORE >> Doorbell >> DoorbellHandle@NIC >> QueueManager >> NICOutQueue@NIC >> Classify@NIC >> [get,set,new_seg];
  }
}
// NIC parser: FROM_NET, doorbell, queue_manager, DMA***
// output port that branches out according to data type?
// Doorbell [out(db1)] >> DoorbellHandle1 [out(int,entry1)] >> QueueManager [out(entry1)] >> Task1
// Doorbell [out(db2)] >> DoorbellHandle2 [out(int,entry2)] >> QueueManager [out(entry2)] >> Task2

Element QueueManager@NIC {
  input port in(int n, ?);
  output port out(?); // whatever the parser outputs?
}

Element NICSteeringQueue@NIC uses Queue { // "uses" states
  input port in(eqe_entry p, size_t size, uint6_t core_id);

  run {
    (eqe_entry p, size_t size, uint6_t core_id) = in();
    queue q = queues_rx[core_id];

   if(queue is not full) {
     DMA_write(q.base + q.head, psize, p);
     // update queue
   }
   // else drop
  }
}

Element DoorbellHandle@NIC uses Queue {
  input port in(doorbell);
  output port out(int n, entry e, int size);
  
  run {
    doorbell db = in();
    // update rx_head    
    if(db.rx_head != -1)
      queues_rx[db.core_id].head = db.rx_head;
    if(db.tx_tail != -1) 
      queues_tx[db.core_id].head = db.tx_tail;
    if(db.tx_n > 0) {
      // for i in range(db.tx_n):
      //   DMA read an entry from notification queue
      // for loop is prohibited @NIC
      out(n,???);
    }
  }
}
