app_new_flow >>re syscall1 >>re new_flow_client@KERNEL >>2 doorbell3 >> send_handshake_syn@NIC >> TO_NET;


AppNewFlow app_new_flow;
API AppNewFlow@APP_CORE {

  .return {
    port in(queue*); // in_return
    port out(queue*);

    .run() { out(in()); }
  }
}

Element NewFlowClient@KERNEL {
  port in(2tuple_opaque);
  port in_return(queue*,seq,ack);
  port out(uint32_t,2tuple_opaque);

  .run() {
    queue *q = allocate queue
    x = combine in(2tuple) and in(opaque)
    out(addr,x);
    in_return(q);
  }

}

// Flow: app_new_flow >> syscall >> new_flow_client >> doorbell >> new_flow_client >> syscall >> app_new_flow
// Go until doorbell because the first half of doorbell is still on the same thread.
// Essentially there is this implicit reverse flow within each hardware device.
// This is not true for @NIC???



exception >> exception_queue@NIC >> DMA_write >>pull kernel_entry
kernel_entry >> recv_handshake_syn_ack@KERNEL // case: new flow(client)
kernel_entry >> recv_handshake_syn@KERNEL // case: new flow (server)
kernel_entry >> recv_handshake_ack@KERNEL // case: new flow (server)

Element KernelEntry {
  port in_pull(uint32_t);
  port in(queue_entry);
  port out(…);
}

// Pulling elements
// @NIC: none
// @APP_CORE/APP: API nodes
// @KERNEL: need scheduling
// @APP_CORE/APP non-API node: need scheduling