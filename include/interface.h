Flow Doorbell {
  port in(uint32_t, object);
  port out(uint32_t, object); // Does doorbell need to integrate parsing in order to reconstruct val?
  
  .flow {
    PCIeSend pcie_send;
    PCIeRecv pcie_recv;
    in(0), in(1) >> pcie_send@HOST; pcie_recv@NIC >> out(0), out(1);
  }
}

Element PCIeSend {
  port in(uint32_t, object);

  .run {
    write in(1) to address in(0)
  }
}


Element PCieRecv {
  port out(uint32_t, object);
  ???
}