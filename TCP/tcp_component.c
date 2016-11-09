// main
FROM_NET >> CheckConnection@NIC;
CheckConnection@NIC (known) >> KnownConnection@NIC (send_ack) >> TO_NET;

// common-case receive
KnownConnection@NIC (in_order) >> (in) InOrder@NIC (to_app) >> (nic_put) MainQueue (app_get) 
  <> recvInorder@API;

// out-of-order
KnownConnection@NIC (out_of_order) >> (in) OutOfOrder@NIC >> (nic_put) ExceptionQueue (kernel_get) 
  <> KernelEntry@KERNEL (OOO) >> (in) OOO@KERNEL >> (kernel_put) ContextQueue (app_get) <> recvOOO@API;
(in) OOO@KERNEL >> (kernel_put) ExceptionQUEUE (nic_get) 
  >> Classifier@NIC (fix_ooo) >> UpdateFlow@NIC;

// common-case send
send@API >> (app_put) MainQueue (nic_get) >> CreateResponse@NIC >> TO_NET;

// new connection (client)
new_connecion@API >> (client_request) NewConnection@APP_CORE >> (app_put) ContextQueue (kernel_get)
  <> KernelEntry@KERNEL >> (client_new_connection) ConnectionManager@KERNEL >> (kernel_put) ExceptionQueue (nic_get)
  >> Classifier@NIC >> (hs_syn) HandShake@NIC >> TO_NET;
FROM_NET >> CheckConnection@NIC (unknown) >> UnknownConnection@NIC >> (nic_put) ExceptionQueue (kernel_get)
  <> KernelEntry@KERNEL >> (hs_syn_ack) ConnectionManager@KERNEL >> (kernel_put) ExceptionQueue (nic_get)
  >> Classifier@NIC >> (hs_ack) HandShake@NIC >> TO_NET;
(hs_syn_ack) ConnectionManager@KERNEL >> (kernel_put) ContextQueue (app_get)
  <> NewConnection@APP_CORE (check_client_request) <> new_connection_ready@API;

// new connection (server)
listen@API >> (server_listen) NewConnection@APP_CORE >> (app_put) ContextQueue (kernel_get)
  <> KernelEntry@KERNEL >> (server_listen) ConnectionManager@KERNEL;
ExceptionQueue (kernel_get)
  <> KernelEntry@KERNEL >> (hs_syn) ConnectionManager@KERNEL >> (kernel_put) ExceptionQueue (nic_get)
  >> Classifier@NIC >> (hs_syn_ack) HandShake@NIC >> TO_NET;
ExceptionQueue (kernel_get)
  <> KernelEntry@KERNEL >> (hs_ack) ConnectionManager@KERNEL >> (kernel_put) ContextQueue (app_get)
  <> NewConnection@APP_CORE (check_and_accept) <> check_and_accept@API;

// new application thead
init_NIC_interface@API >> (init_worker) APPManager@APP_CORE >> ContextQueue??? ;
// There is no ContextQueue between this worker thread and kernel yet. How do they communicate?
  
// congestion control

// epoll
int epoll_create(int size) 
int epoll_create1() 
epoll_ctl // register EPOLLIN and EPOLLOUT on all payload buffer
epoll_wait
epoll_pwait
  
// Seem like we need global state for TCP because many action require flow state
