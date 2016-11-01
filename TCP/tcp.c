app_new_flow@call >> syscall1@call >> new_flow_client@KERNEL >> syscall1@return >> app_new_flow@return;
new_flow_client@KERNEL >> doorbell3 >> send_handshake_syn@NIC >> TO_NET;


AppNewFlow app_new_flow;
API AppNewFlow@APP_CORE {

  .return {
    port in(queue*);
    port out(queue*);

    .run() { out(in()); }
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
