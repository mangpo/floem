
/**********************************************************************/
/* Receiving */


ExtractKey extract_key;
SteeringQueue steering_queue;
APPRecv app_recv;

FROM_NET >> extract_key@NIC >>2 steering_queue; // extract_key sends two tokens to 
app_recv@call >> steering_queue >> app_recv@return;


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
  port in(packet_mod, uint32_t, signal_t); 
  port out(packet_mod);

  .flow {
    EnqueueRx enqueue_rx;
    DequeueRx dequeue_rx;
    in(0), in(1) >> enqueue_rx@NIC | in(2) >> dequeue_rx@APP_CORE >> out();
    // OR in(packet_raw), in(uint32_t) >> enqueue_rx@NIC | in(signal_t) >> dequeue_rx@APP_CORE >> out();
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
  port out(packet_mod);
  
  .run {
    get packet
    update head
  }
}

API APPRecv@APP_CORE {
  .call { 
    port in(); // argument types of API function
    port out();

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

app_send@call >> tx_queue >> repacket@NIC >> TO_NET;
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
    // Does doorbell need to integrate parsing in order to reconstruct val???
  }
}

Element EnqueueTx@APP_CORE {
  port in(packet_ret);
  port out(uint32_t, doorbell_t);
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
  port in(uint32_t, doorbell_t);
  port out(packet_ret);

  .run {
    doorbell_t db = in(doorbell_t);
    rx_head = db.rx_head;
    while(tx_tail < db.tx_tail) {
      DMA: read packet from circular queue
      out(packet);
    } // ??? loop here!!!
    tx_tail = db.tx_tail;
  }
}

Element Repacket@NIC {
  port in(packet_ret);
  port out(full_packet_ret);
}
