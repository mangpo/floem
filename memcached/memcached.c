ExtractKey extract_key;
SteeringQueue steering_queue;

FROM_NET >> extract_key@NIC >>2 steering_queue; // extract_key sends two tokens to steering_queue
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
  port in(packet_mod, uint32_t, signal_t); // 2 input ports
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
    put packet in(0) to circular queue whose core id = key in(1)
    update tail
    ??? how does NIC update head ???
  }
}

Element DequeueTx@APP_CORE {
  port in(signal_t);
  port out(packet_mod);
  
  .run {
    get packet
    update head
  }
}

API app_recv@APP_CORE {
  .call { 
    port in(); // argument types of API function
    port out(signal_t);

    .run { out(null); }
  }

  .return { 
    port in(packet_mod);
    port out(packet_mod); // return type of API function
   
    .run { out(in()); }
  }
}
