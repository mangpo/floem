from dsl import *
from compiler import Compiler
import net

n_cores = 1

class protocol_binary_request_header_request(State):
    magic = Field(Uint(8))
    opcode = Field(Uint(8))
    keylen = Field(Uint(16))
    extlen = Field(Uint(8))
    datatype = Field(Uint(8))
    status = Field(Uint(16))
    bodylen = Field(Uint(32))
    opaque = Field(Uint(32))
    cas = Field(Uint(64))

    # Tell compiler not to generate this struct because it's already declared in some other header file.
    def init(self): self.declare = False

class protocol_binary_request_header(State):
    request = Field(protocol_binary_request_header_request)

    def init(self): self.declare = False

class iokvs_message(State):
    ether = Field('struct ether_hdr')
    ipv4 = Field('struct ipv4_hdr')
    dup = Field('struct udp_hdr')
    mcudp = Field('memcached_udp_header')
    mcr = Field(protocol_binary_request_header)
    payload = Field(Array(Uint(8)))

    def init(self): self.declare = False

class item(State):
    next = Field('struct _item')
    hv = Field(Uint(32))
    vallen = Field(Uint(32))
    refcount = Field(Uint(16))
    keylen = Field(Uint(16))
    flags = Field(Uint(32))

    def init(self): self.declare = False

class MyState(State):
    pkt = Field(Pointer(iokvs_message))
    pkt_buff = Field('void*')
    it = Field(Pointer(item), shared='data_region')
    key = Field('void*', size='state->pkt->mcr.request.keylen')
    hash = Field(Uint(32))
    core = Field(Uint(16))
    vallen = Field(Uint(32))

class Schedule(State):
    core = Field(Int)
    def init(self): self.core = 0

class ItemAllocators(State):
    ia = Field('struct item_allocator*')

    def init(self):
        self.ia = 'get_item_allocators()'

item_allocators = ItemAllocators()

class segments_holder(State):
    segbase = Field(Uint(64))
    seglen = Field(Uint(64))
    offset = Field(Uint(64))
    next = Field('struct _segments_holder*')
    last = Field('struct _segments_holder*')

class main(Flow):
    state = PerPacket(MyState)

    class SaveID(Element):
        def configure(self):
            self.inp = Input(Int)

        def impl(self):
            self.run_c(r'''''')

    class SaveState(Element):
        def configure(self):
            self.inp = Input(SizeT, "void *", "void *")
            self.out = Output()

        def impl(self):
            self.run_c(r'''''')

    class GetPktBuff(Element):
        def configure(self):
            self.inp = Input()
            self.out = Output("void*", "void*")

        def impl(self):
            self.run_c(r'''''')

    class CheckPacket(Element):
        def configure(self):
            self.inp = Input(SizeT, 'void*', 'void*')
            self.out = Output(SizeT, 'void*', 'void*')
            self.slowpath = Output( 'void*', 'void*')
            self.drop = Output('void*', 'void*')

        def impl(self):
            self.run_c(r'''''')


    class Classifer(Element):
        def configure(self):
            self.inp = Input()
            self.out_get = Output()
            self.out_set = Output()

        def impl(self):
            self.run_c(r'''''')

    class GetKey(ElementOneInOut):
        def impl(self):
            self.run_c(r'''''')

    class GetCore(ElementOneInOut):
        def impl(self):
            self.run_c(r'''''' % ('%', n_cores, '%d', '%d'))

    ######################## hash ########################

    class JenkinsHash(ElementOneInOut):
        def impl(self):
            self.run_c(r'''''')

    class HashGet(Element):
        def configure(self):
            self.inp = Input()
            self.out = Output()
            self.null = Output()

        def impl(self):
            self.run_c(r'''''')

    class HashPut(ElementOneInOut):
        def impl(self):
            self.run_c(r'''''')


    ######################## responses ########################

    class Scheduler(Element):
        this = Persistent(Schedule)

        def configure(self):
            self.out = Output(Int)
            self.this = Schedule()

        def impl(self):
            self.run_c(r'''''' % ('%', n_cores))

    class SizeGetResp(Element):
        def configure(self):
            self.inp = Input()
            self.out = Output(SizeT)

        def impl(self):
            self.run_c(r'''''')

    class PrepareGetResp(Element):
        def configure(self):
            self.inp = Input(SizeT, 'void*', 'void*')
            self.out = Output(SizeT, Pointer(iokvs_message), 'void*')

        def impl(self):
            self.run_c(r'''''')

    class SizeGetNullResp(Element):
        def configure(self):
            self.inp = Input()
            self.out = Output(SizeT)

        def impl(self):
            self.run_c(r'''
//printf("size get null\n");
            size_t msglen = sizeof(iokvs_message) + 4;
            output { out(msglen); }
            ''')

    class PrepareGetNullResp(Element):
        def configure(self):
            self.inp = Input(SizeT, 'void*', 'void*')
            self.out = Output(SizeT, Pointer(iokvs_message), 'void*')

        def impl(self):
            self.run_c(r'''''')

    class SizeSetResp(Element):
        def configure(self):
            self.inp = Input()
            self.out = Output(SizeT)

        def impl(self):
            self.run_c(r'''''')

    class SizePktBuffSetResp(Element):
        def configure(self):
            self.inp = Input()
            self.out = Output(SizeT, 'void*', 'void*')

        def impl(self):
            self.run_c(r'''''')

    class PrepareSetResp(Element):
        def configure(self, status):
            self.inp = Input(SizeT, 'void*', 'void*')
            self.out = Output(SizeT, Pointer(iokvs_message), 'void*')
            self.status = status
            # PROTOCOL_BINARY_RESPONSE_SUCCESS
            # PROTOCOL_BINARY_RESPONSE_ENOMEM

        def impl(self):
            self.run_c(r'''''' % self.status)

    class SizePktBuff(Element):
        def configure(self):
            self.inp = Input(SizeT)
            self.out = Output(SizeT, 'void*', 'void*')

        def impl(self):
            self.run_c(r'''''')

    class PrepareHeader(Element):
        def configure(self):
            self.inp = Input(SizeT, Pointer(iokvs_message), "void *")
            self.out = Output(SizeT, "void *", "void *")

        def impl(self):
            self.run_c(r'''''')

    class HandleArp(Element):
        def configure(self):
            self.inp = Input("void *", "void *")
            self.out = Output(SizeT, "void *", "void *")
            self.drop = Output("void *", "void *")

        def impl(self):
            self.run_c(r'''''')


    class PrintMsg(Element):
        def configure(self):
            self.inp = Input(SizeT, "void *", "void *")
            self.out = Output(SizeT, "void *", "void *")

        def impl(self):
            self.run_c(r'''''')



    ######################## item ########################
    class GetItemSpec(Element):
        this = Persistent(ItemAllocators)
        def states(self):
            self.this = item_allocators

        def configure(self):
            self.inp = Input()
            self.out = Output()
            self.nothing = Output()

        def impl(self):
            self.run_c(r'''''')


    class Unref(ElementOneInOut):
        def impl(self):
            self.run_c(r'''''')

    class Clean(Element):
        def configure(self, val):
            self.inp = Input()
            self.out = Output(Bool)
            self.val = val

        def impl(self):
            self.run_c(r'''''' % self.val)

    class Drop(Element):
        def configure(self):
            self.inp = Input()

        def impl(self):
            self.run_c("")

    class CleanLog(Element):
        this = Persistent(ItemAllocators)

        def states(self):
            self.this = item_allocators

        def impl(self):
            self.run_c(r'''''')

    def impl(self):
        MemoryRegion('data_region', 2 * 1024 * 1024 * 512, init='ialloc_init(data_region);') #4 * 1024 * 512)


        ######################## NIC Rx #######################
        class process_one_pkt(Pipeline):
            def impl(self):
                from_net = net.FromNet('from_net',configure=[32])
                from_net_free = net.FromNetFree('from_net_free')
                to_net = net.ToNet('to_net', configure=['from_net',32])
                classifier = main.Classifer()
                check_packet = main.CheckPacket()
                hton1 = net.HTON(configure=['iokvs_message'])
                hton2 = net.HTON(configure=['iokvs_message'])

                prepare_header = main.PrepareHeader()
                display = main.PrintMsg()
                drop = main.Drop()
                save_id = main.SaveID()

                self.core_id >> save_id

                # from_net
                from_net >> hton1 >> check_packet >> main.SaveState() \
                >> main.GetKey() >> main.JenkinsHash() >> classifier
                from_net.nothing >> drop

                # get
                hash_get = main.HashGet()
                get_response = main.PrepareGetResp()
                classifier.out_get >> hash_get >> main.SizeGetResp() >> main.SizePktBuff() >> get_response >> prepare_header
                get_response >> main.Unref() >> main.Drop()

                # get (null)
                hash_get.null >> main.SizeGetNullResp() >> main.SizePktBuff() >> main.PrepareGetNullResp() >> prepare_header

                # set
                get_item = main.GetItemSpec()
                set_response = main.PrepareSetResp(configure=['PROTOCOL_BINARY_RESPONSE_SUCCESS'])
                classifier.out_set >> get_item >> main.HashPut() >> main.Unref() >> main.SizeSetResp() \
                >> main.SizePktBuff() >> set_response >> prepare_header

                # set (unseccessful)
                set_reponse_fail = main.PrepareSetResp(configure=['PROTOCOL_BINARY_RESPONSE_ENOMEM'])
                get_item.nothing >> main.SizeSetResp() >> main.SizePktBuff() >> set_reponse_fail >> prepare_header

                # exception
                arp = main.HandleArp()
                check_packet.slowpath >> arp >> to_net
                arp.drop >> from_net_free
                check_packet.drop >> from_net_free

                # send
                prepare_header >> display >> hton2 >> to_net

                # clean log
                clean_log = main.CleanLog()

                run_order(save_id, from_net)
                run_order([to_net, from_net_free, drop], clean_log)

        process_one_pkt('process_one_pkt', process='dpdk', cores=range(n_cores))

master_process('dpdk')


######################## Run test #######################
c = Compiler(main)
c.include = r'''
#include "nicif.h"
#include "iokvs.h"
#include "protocol_binary.h"
'''
c.generate_code_as_header()
c.depend = ['jenkins_hash', 'hashtable', 'ialloc', 'settings', 'dpdk']
c.compile_and_run('test_no_steer')
