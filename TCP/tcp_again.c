// how to use states @APP and states @APP_CORE
// flow state in NIC
// queue per core
// connection


///////////// Connection States ////////////////
struct NICConnection {
  uint64_t opaque;
  uint64_t rx_start, tx_start;
  uint32_t rx_size, tx_size;
  uint32_t rx_pos, tx_pos;
  uint32_t seq, ack;
  uint1_t ooo;
  uint16_t db;
}

struct APPConnection { 
  uint64_t opaque;
  uint64_t rx_start, tx_start;
  uint32_t rx_size, tx_size;
  uint32_t rx_pos, tx_pos;
  uint32_t seq, ack;
  uint16_t db;
}

State NICConnections@NIC {
  NICConnection connections[N];
  Map<uint32_t,uint16_t> tuple2connection;
}

State APPConnections@APP { // per application
  int app_id;
  APPConnection* connections[N];
  Map<uint32_t,uint16_t> tuple2connection;
}


///////////// Notification & Context Queue ////////////////
struct NICNotify { 
  uint64_t rx_start, tx_start;
  uint32_t rx_size, tx_size;
  uint32_t rx_head, rx_tail;
  uint32_t tx_head, tx_tail;
}
struct APPNotify { 
  uint64_t rx_start, tx_start;
  uint32_t rx_size, tx_size;
  uint32_t rx_head, tx_tail;
}

State Context@NIC {
  NICNotify notifications[M];
  NICException exception;
}

State Context@APP_CORE { // per worker thread
  APPNotify notification;
  APPContext context;
}

State Context@KERNEL {
  KernelException exception;
  KernelConext context[M];
}

// new worker thread v1
init_worker@API >> Init@APP_CORE >> syscall >> NewAppThread@KERNEL >> sysreturn >> InitFinalize@APP_CORE >> init_worker@API; 
// syscall & sysreturn = UNIX domain socket. They take any number of arguments and data types.
// notion of thread of control is gone.

Element Init@APP_CORE uses APPConnections {
  input port in();
  output port out(int app_id);

  run {
    initialize(); // allocate states @APP_CORE
    out(app_id);
  }
}

Element InitFinalize@APP_CORE uses Context {
  input port in(APPContext, APPnotify);
  output port out(APP_CORE*);
  
  run {
    (APPContext context, APPnotify notification) = in();
    this.context = context;
    this.notification = notification;
    out();
  }
}

// new worker thread v1 (use low-level elements)
init_worker@API >> Init >> init_worker@API;

Composite Init {
  input port in();
  output port out();

  Implement {
    [in] >> Init1@APP_CORE >> socket_write >> [done] Wait@APP_CORE; 
    KernelEntry >> socket_read >> NewWorkerThread@KERNEL >> socket_write;
    Wait@APP_CORE >> socket_read >> Status@APP_CORE [out] >> [out];
    Status@APP_CORE [read] >> socket_read; // loop
  }
}

// new worker thread v2 (use syscall composit element)
init_worker@API >> Init1@APP_CORE >> [in] Syscall [out] >> Init2@APP_CORE >> init_worker@API;
KernelEntry@KERNEL >> [ker-in] Syscall [A] >> NewThread@KERNEL >> [B] Syscall;

// net worker thread v3 (use function call)
init_worker@API >> Init >> init_worker@API;

Composite Init {
  input port in();
  output port out();

  Implement {
    [in] >> InitRequest@APP_CORE >> [out]; 
    KernelEntry@KERNEL >> WorkerAllocation@KERNEL;
  }
}

Element InitRequest@APP_CORE uses Context {
  input port in();
  output port out();

  run {
    initialize(); // allocate states @APP_CORE
    UNIX_socket_send(socket, message);
    (context, notification) = UNIX_socket_recv(socket);
  }
}

// main
FROM_NET >> CheckConnection@NIC;
CheckConnection@NIC [known] >> KnownConnection@NIC [send_ack] >> TO_NET;

// common-case receive
KnownConnection@NIC [in_order] >> InOrder@NIC >> [in] MainQueue;
recv_inorder@API >> [dequeue] MainQueueToAPP [out] >> recv_inorder@API;

// out-of-order
KnownConnection@NIC [out_of_order] >> OutOfOrder@NIC >> [in] ExceptionQueueToKER; 
  KernelEntry@KERNEL >> [dequeue] ExceptionQueueToKER >> OOO@KERNEL >> ContextQueueToAPP;
  recv_ooo@API >> [dequeue] ContextQueueToAPP >> recv_ooo@API; // what if context queue contains something else?
  OOO@KERNEL >> ExceptionQueueToNIC (fix_ooo) >> UpdateFlow@NIC;

// common-case send
send@API >> MainQueueTNIC >> CreateResponse@NIC >> TO_NET;

// new connection (client)
new_connecion@API >> ClientConnect@APP_CORE >> [in] ContextQueueToKER;
  KernelEntry@KERNEL >> [dequeue] ContextQueueToKER [client_new_connection] >> ClientConnect@KERNEL 
  >> ExceptionQueueToNIC [hs_syn] >> SendSyn@NIC >> TO_NET;
FROM_NET >> CheckConnection@NIC [unknown] >> UnknownConnection@NIC >> ExceptionQueueToKER;
  KernelEntry@KERNEL >> ExceptionQueueToKER [hs_syn_ack] 
  >> SynAck@KERNEL [to_nic] >> ExceptionQueueToNIC [hs_ack] >> SendAck@NIC >> TO_NET;
     SynAck@KERNEL [to_app] >> [in] ContextQueueToAPP;
  new_connection_ready@API >> [dequeue] ContextQueueToAPP >> new_connection_ready@API; // what if context queue contains something else?

// new connection (server)
listen@API >> ServerListen@APP_CORE >> [in] ContextQueueToKER;
  KernelEntry@KERNEL >> [dequeue] ContextQueueToKER [server_listen] >> ServerListen@KERNEL;
KernelEntry@KERNEL >> [dequeue] ExceptionQueueToKER [hs_syn] >> Syn@KERNEL >> ExceptionQueueToNIC [hs_syn_ack] >> SendSynAck@NIC >> TO_NET;
KernelEntry@KERNEL >> [dequeue] ExceptionQueueToKER [hs_ack] >> Ack@KERNEL >> [in] ContextQueueToAPP;
check_and_accept@API >> [dequeue] ContextQueueToAPP >> check_and_accept@API; // what if context queue contains something else?

// congestion control

// epoll
int epoll_create(int size) 
int epoll_create1() 
epoll_ctl // register EPOLLIN and EPOLLOUT on all payload buffer
epoll_wait
epoll_pwait

