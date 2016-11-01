
// x = out_pull(); // maybe we shouldn’t allow this (chain of pullings), but okay if it’s after in()???
// in_pull(x);
// x = in();

// out(x);
// x = out_return();
// in_return(x); // support chain or returns

/**********************************************************************/
/* Receiving */


ExtractKey extract_key;
SteeringQueue steering_queue;
APPRecv app_recv;

FROM_NET >> extract_key@NIC >>2 steering_queue >>pull app_recv;


Element ExtractKey@NIC {
  port in(udp_t);
  port out(packet_mod);

  .run {
    compute key
    append key to packet
    remove some fields
  }
}

Flow SteeringQueue {
  port in(packet_mod, uint32_t);
  port out(packet_mod);

  .flow {
    EnqueueRx enqueue_rx;
    DequeueRx dequeue_rx;
    in(0), in(1) >> enqueue_rx@NIC >> DMA_write >>pull dequeue_rx@APP_CORE >> out();
  }
}


Element EnqueueRx@NIC {
  port in(packet_mod, uint32_t);

  .run {
    DMA: put packet in(0) to circular queue whose core id = key in(1)
    update tail locally
  }
}

Element DequeueRx@APP_CORE {
  port in(signal_t);
  port out_pull(uint32_t);
  port out(packet_mod);
  
  .run {
    in_pull(addr);
    packet = in();
    update head
  }
}

API APPRecv@APP_CORE {
  .call { 
    port in(); // argument types of API function
    port out(); // pull

    .run { out(); }
  }

  .return { 
    port in(packet_mod);
    port out(packet_mod); // return type of API function
   
    .run { out(in()); }
  }
}


/**********************************************************************/
/* Receiving */

TxQueue tx_queue;
Repacket re packet;
APPSend app_send;

app_send >> tx_queue >> repacket@NIC >> TO_NET;
// implicit return when @APP_CORE is done.

API APPSend@APP_CORE {
  .call { 
    port in(packet_ret);
    port out(packet_ret);

    .run { out(in()); }
  }
}

Flow TxQueue {
  port in(packet_ret);
  port out(packet_ret);

  .flow {
    EnqueueTx enqueue_tx;
    DequeueTx dequeue_tx;
    Doorbell doorbell;
    in() >> enqueue_tx@APP_CORE >>2 doorbell >>2 dequeue_tx@NIC >> out();
    enqueue_tx@APP_CORE >> DMA_read >>pull dequeue_tx@NIC;
    // Does doorbell need to integrate parsing in order to reconstruct val???
  }
}

Element EnqueueTx@APP_CORE {
  port in(packet_ret);
  port out(uint32_t, doorbell_t,queue_entry);
  .run { 
    put packet in(0) to circular queue
    update tail
    BATCH: 
    - multiple packets
    - Rx head
    - Tx tail
    write to doorbell
  }
}

Element DequeueTx@NIC {
  port in_pull(null, null, uint32_t);
  port in(uint32_t, doorbell_t,queue_entry);
  port out(packet_ret);

  .run {
    doorbell_t db = in(doorbell_t);
    rx_head = db.rx_head;
    while(tx_tail < db.tx_tail) {
      DMA: read packet from circular queue 
      in_pull(queue_entry, rx_head);
      entry = in(queue_entry);
      out(packet);
      rx_head += …
    } // ??? loop here!!!
    tx_tail = db.tx_tail;
  }
}

Element Repacket@NIC {
  port in(packet_ret);
  port out(full_packet_ret);
}
