// client->server
app_new_flow_init@call >> enqueue_app2ker@APP_CORE | kernel_context@KERNEL >> dequeue_app2ker@KERNEL >> new_flow_client@KERNEL >> doorbell3 >> send_handshake_syn@NIC >> TO_NET;


exception >> exception_queue@NIC | kernel_entry@KERNEL >> recv_handshake_syn_ack@KERNEL >> new_flow_confirm@KERNEL >> doorbell4 >> nic_new_flow@NIC >> send_handshake_ack@NIC >> TO_NET;
new_flow_confirm@KERNEL >> enqueue_ker2app@KERNEL |  app_new_flow_ready@call >> dequeue_ker2app@APP_CORE >> app_new_flow_ready@return;



AppNewFlowInt app_new_flow_init;
API AppNewFlowInit@APP_CORE {
  .call {
    port in(socket,ip,port);
    port out(queue_entry);

    .run { out(create entry from in(0), in(1), in(2)); }
  }

  // return void
}

AppNewFlowReady app_new_flow_ready;
API AppNewFlowReady@APP_CORE {
  .call {
    port in();
    port out(command_type);

    .run { out(0); }
  }

  .return {
    port in(queue_entry);
    port out(socket,in,port,queue*);

    .run { out(extract socket,in,port,queue from in()); }
  }
}

// app_new_flow, new_flow_client, and the first half of doorbell3 run on the same CPU thread. Therefore, syscall1@return actually happens after the write to doorbell.
// There is no semantics different but the meaning of execution order is diffident.
// Is this okay? Or maybe we just need to change the meaning of execution order to fit this behavior


Interval@KERNEL interval(1000); // generate signal every 1000 ms
Kernel_entry kernel_entry;
interval@KERNEL >> kernel_entry@KERNEL;


 exception >> exception_queue@NIC  | kernel_entry >> recv_handshake_syn_ack@KERNEL // case: new flow(client)
[ exception >> exception_queue@NIC ] kernel_entry >> recv_handshake_syn@KERNEL // case: new flow (server)
[ exception >> exception_queue@NIC ] kernel_entry >> recv_handshake_ack@KERNEL // case: new flow (server)

Element Kernel_entry {
  .run {
    Exception_t exp = get an entry from exception.queue;
    int command = exp.command;
    switch(command) {
      Case 0: out(recv_handshake_syn, exp); break;
      Case 1: out(recv_handshake_syn_ack, exp); break;
      Case 2: out(recv_handshake_ack, exp); break;
      Case 3: out(fix_order, exp); break;
      ...
  }
}
