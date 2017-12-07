app_new_flow >>re syscall1 >>re new_flow_client@KERNEL >>2 doorbell3 >> send_handshake_syn@NIC >> TO_NET;

// client->server
app_new_flow_init >> context_enqueue@APP_CORE | kernel_context@KERNEL (API) >> context_dequeue@KERNEL >> classify@KERNEL >> new_flow_client@KERNEL >> doorbell3 >> send_handshake_syn@NIC >> TO_NET;


[exception >> exception_enqueue@NIC >> DMA_write >>pull kernel_entry >>] recv_handshake_syn_ack@KERNEL >> new_flow_confirm@KERNEL >> doorbell4 >> nic_new_flow@NIC >> send_handshake_ack@NIC >> TO_NET;
new_flow_confirm@KERNEL >> enqueue_ker2app@KERNEL |  dequeue_ker2app@APP_CORE >>pull app_new_flow_ready;


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

// Consider having API for kernel
// external part may have interrupt, use external libraries
