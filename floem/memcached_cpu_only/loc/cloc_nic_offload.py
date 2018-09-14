class QID(Element):
    def configure(self):
        self.inp = Input()
        self.out = Output()

    def impl(self):
        self.run_c(r'''
state->qid = state->hash %s %d;
output { out(); }
''' % ('%', n_cores))


        # Queue


RxEnq, RxDeq, RxScan = queue_smart.smart_queue("rx_queue", entry_size=192, size=256, insts=n_cores,
                                               channels=2, enq_blocking=True, enq_atomic=True, enq_output=False)
rx_enq = RxEnq()
rx_deq = RxDeq()

TxEnq, TxDeq, TxScan = queue_smart.smart_queue("tx_queue", entry_size=192, size=256, insts=n_cores,
                                               channels=2, checksum=False, enq_blocking=True, deq_atomic=True,
                                               enq_output=True)
tx_enq = TxEnq()
tx_deq = TxDeq()


######################## CPU #######################
class process_one_pkt(Pipeline):
    def impl(self):
        self.core_id >> main.CleanLog() >> rx_deq
        rx_deq.out[0] >> main.HashGet() >> tx_enq.inp[0]
        rx_deq.out[1] >> main.GetItemSpec() >> main.HashPut() >> tx_enq.inp[1]
        tx_enq.done >> main.Unref() >> library.Drop()


######################## NIC #######################
class nic_rx(Pipeline):
    def impl(self):
        from_net = net.FromNet('from_net')
        from_net_free = net.FromNetFree('from_net_free')
        to_net = net.ToNet('to_net', configure=['from_net'])
        classifier = main.Classifer()
        check_packet = main.CheckPacket()
        hton = net.HTON(configure=['iokvs_message'])
        arp = main.HandleArp()
        drop = main.Drop()

        # from_net
        from_net >> hton >> check_packet >> main.SaveState() >> main.GetKey() >> main.JenkinsHash() >> classifier
        from_net.nothing >> drop

        classifier.out_get >> main.Key2State() >> CacheGetStart() >> main.QID() >> rx_enq.inp[0]
        classifier.out_set >> main.KV2State() >> CacheSetStart() >> main.QID() >> rx_enq.inp[1]

        # exception
        check_packet.slowpath >> arp >> to_net
        arp.drop >> from_net_free
        check_packet.drop >> from_net_free


class nic_tx(Pipeline):
    def impl(self):
        prepare_header = main.PrepareHeader()
        get_result = main.GetResult()
        get_response = main.PrepareGetResp()
        get_response_null = main.PrepareGetNullResp()
        set_result = main.SetResult()
        set_response = main.PrepareSetResp(configure=['PROTOCOL_BINARY_RESPONSE_SUCCESS'])
        set_reponse_fail = main.PrepareSetResp(configure=['PROTOCOL_BINARY_RESPONSE_ENOMEM'])
        hton = net.HTON(configure=['iokvs_message'])
        to_net = net.ToNet('to_net', configure=['from_net'])

        self.core_id >> main.TxScheduler() >> tx_deq

        # get
        tx_deq.out[0] >> CacheGetEnd() >> get_result
        get_result.hit >> main.SizeGetResp() >> main.SizePktBuff() >> get_response >> prepare_header
        get_result.miss >> main.SizeGetNullResp() >> main.SizePktBuff() >> get_response_null >> prepare_header

        # set
        tx_deq.out[1] >> CacheSetEnd() >> set_result
        set_result.success >> main.SizeSetResp() >> main.SizePktBuff() >> set_response >> prepare_header
        set_result.fail >> main.SizeSetResp() >> main.SizePktBuff() >> set_reponse_fail >> prepare_header

        # send
        prepare_header >> hton >> to_net

    nic_rx('nic_rx', device=target.CAVIUM, cores=[nic_threads + x for x in range(nic_threads)])
    nic_tx('nic_tx', device=target.CAVIUM, cores=range(nic_threads))