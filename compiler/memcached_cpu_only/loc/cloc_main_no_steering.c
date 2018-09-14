main () {
(size_t msglen, void* pkt, void* buff) = inp();
iokvs_message* m = (iokvs_message*) pkt;

int type; // 0 = normal, 1 = slow, 2 = drop

if (m->ether.ether_type == htons(ETHER_TYPE_IPv4) &&
    m->ipv4.next_proto_id == 17 &&
    m->ipv4.dst_addr == settings.localip &&
    m->udp.dst_port == htons(11211) &&
    msglen >= sizeof(iokvs_message))
{
    uint32_t blen = m->mcr.request.bodylen;
    uint32_t keylen = m->mcr.request.keylen;

        /* Ensure request is complete */
        if (blen < keylen + m->mcr.request.extlen ||
            msglen < sizeof(iokvs_message) + blen) {
            type = 2;
        }
        else if (m->mcudp.n_data != htons(1)) {
            type = 2;
        }
        else if (m->mcr.request.opcode != PROTOCOL_BINARY_CMD_GET &&
                 m->mcr.request.opcode != PROTOCOL_BINARY_CMD_SET) {
            type = 2;
        }
        else {
            type = 0;
        }
} else {
  type = 1;
}

output switch {
    case type==0: out(msglen, m, buff);
    case type==1: slowpath(m, buff);
    else: drop(m, buff);
}

uint8_t cmd = state->pkt->mcr.request.opcode;
//printf("receive: %d\n", cmd);

output switch{
  case (cmd == PROTOCOL_BINARY_CMD_GET): out_get();
  case (cmd == PROTOCOL_BINARY_CMD_SET): out_set();
  // else drop
}

state->key = state->pkt->payload + state->pkt->mcr.request.extlen;
output { out(); }

int core = state->hash %s %d;;
state->core = core;
//printf("hash = %s, core = %s\n", state->hash, core);
            output { out(); }

state->hash = jenkins_hash(state->key, state->pkt->mcr.request.keylen);
//printf("hash = %d\n", hash);
output { out(); }

item* it = hasht_get(state->key, state->pkt->mcr.request.keylen, state->hash);
//printf("hash get\n");
state->it = it;

output switch { case it: out(); else: null(); }

hasht_put(state->it, NULL);
output { out(); }

this->core = (this->core + 1) %s %s;
output { out(this->core); }

//printf("size get\n");
    size_t msglen = sizeof(iokvs_message) + 4 + state->it->vallen;
    state->vallen = state->it->vallen;
    output { out(msglen); }

        (size_t msglen, void* pkt, void* pkt_buff) = inp();

        iokvs_message *m = pkt;
        //memcpy(m, &iokvs_template, sizeof(iokvs_message));
        item* it = state->it;

        m->mcr.request.magic = PROTOCOL_BINARY_RES;
        m->mcr.request.opcode = PROTOCOL_BINARY_CMD_GET;
        m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
        m->mcr.request.status = PROTOCOL_BINARY_RESPONSE_SUCCESS;

m->mcr.request.keylen = 0;
m->mcr.request.extlen = 4;
m->mcr.request.bodylen = 4;
*((uint32_t *)m->payload) = 0;
m->mcr.request.bodylen = 4 + state->vallen;
rte_memcpy(m->payload + 4, item_value(it), state->vallen);

output { out(msglen, m, pkt_buff); }
//printf("size get null\n");
            size_t msglen = sizeof(iokvs_message) + 4;
            output { out(msglen); }

            (size_t msglen, void* pkt, void* pkt_buff) = inp();
            iokvs_message *m = pkt;
            //memcpy(m, &iokvs_template, sizeof(iokvs_message));

            m->mcr.request.magic = PROTOCOL_BINARY_RES;
            m->mcr.request.opcode = PROTOCOL_BINARY_CMD_GET;
            m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
            m->mcr.request.status = PROTOCOL_BINARY_RESPONSE_KEY_ENOENT;

    m->mcr.request.keylen = 0;
    m->mcr.request.extlen = 4;
    m->mcr.request.bodylen = 4;
    *((uint32_t *)m->payload) = 0;

    output { out(msglen, m, pkt_buff); }

//printf("size set\n");
            size_t msglen = sizeof(iokvs_message) + 4;
            output { out(msglen); }

            size_t msglen = sizeof(iokvs_message) + 4;
            void* pkt = state->pkt;
            void* pkt_buff = state->pkt_buff;
            output { out(msglen, pkt, pkt_buff); }


(size_t msglen, void* pkt, void* pkt_buff) = inp();
iokvs_message *m = pkt;
//memcpy(m, &iokvs_template, sizeof(iokvs_message));

m->mcr.request.magic = PROTOCOL_BINARY_RES;
m->mcr.request.opcode = PROTOCOL_BINARY_CMD_SET;
m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
m->mcr.request.status = %s;

m->mcr.request.keylen = 0;
m->mcr.request.extlen = 0;
m->mcr.request.bodylen = 0;

output { out(msglen, m, pkt_buff); }

            size_t msglen = inp();
            void* pkt = state->pkt;
            void* pkt_buff = state->pkt_buff;
            output { out(msglen, pkt, pkt_buff); }

        (size_t msglen, iokvs_message* m, void* buff) = inp();

        struct ether_addr mymac = m->ether.d_addr;
        m->ether.d_addr = m->ether.s_addr;
        m->ether.s_addr = mymac; //settings.localmac;
        m->ipv4.dst_addr = m->ipv4.src_addr;
        m->ipv4.src_addr = settings.localip;
        m->ipv4.total_length = htons(msglen - offsetof(iokvs_message, ipv4));
        m->ipv4.time_to_live = 64;
        m->ipv4.hdr_checksum = 0;
        //m->ipv4.hdr_checksum = rte_ipv4_cksum(&m->ipv4);

        m->udp.dst_port = m->udp.src_port;
        m->udp.src_port = htons(11211);
        m->udp.dgram_len = htons(msglen - offsetof(iokvs_message, udp));
        m->udp.dgram_cksum = 0;

        output { out(msglen, (void*) m, buff); }

    (void* pkt, void* buff) = inp();
    iokvs_message* msg = (iokvs_message*) pkt;
    struct arp_hdr *arp = (struct arp_hdr *) (&msg->ether + 1);
    int resp = 0;

    /* Currently we're only handling ARP here */
    if (msg->ether.ether_type == htons(ETHER_TYPE_ARP) &&
            arp->arp_hrd == htons(ARP_HRD_ETHER) && arp->arp_pln == 4 &&
            arp->arp_op == htons(ARP_OP_REQUEST) && arp->arp_hln == 6 &&
            arp->arp_data.arp_tip == settings.localip)
    {
        printf("Responding to ARP\n");
        resp = 1;
        struct ether_addr mymac = msg->ether.d_addr;
        msg->ether.d_addr = msg->ether.s_addr;
        msg->ether.s_addr = mymac;
        arp->arp_op = htons(ARP_OP_REPLY);
        arp->arp_data.arp_tha = arp->arp_data.arp_sha;
        arp->arp_data.arp_sha = mymac;
        arp->arp_data.arp_tip = arp->arp_data.arp_sip;
        arp->arp_data.arp_sip = settings.localip;

        //rte_mbuf_refcnt_update(mbuf, 1);  // TODO

/*
        mbuf->ol_flags = PKT_TX_L4_NO_CKSUM;
        mbuf->tx_offload = 0;
*/
    }

    output switch { 
      case resp: out(sizeof(struct ether_hdr) + sizeof(struct arp_hdr), pkt, buff); 
            else: drop(pkt, buff);
    }

(size_t msglen, void* pkt, void* buff) = inp();
iokvs_message* m = (iokvs_message*) pkt;
uint8_t *val = m->payload + 4;
uint8_t opcode = m->mcr.request.opcode;

/*
if(opcode == PROTOCOL_BINARY_CMD_GET)
    printf("GET -- status: %d, len: %d, val:%d\n", m->mcr.request.status, m->mcr.request.bodylen, val[0]);
else if (opcode == PROTOCOL_BINARY_CMD_SET)
    printf("SET -- status: %d, len: %d\n", m->mcr.request.status, m->mcr.request.bodylen);
*/

output { out(msglen, (void*) m, buff); }

    size_t totlen = state->pkt->mcr.request.bodylen - state->pkt->mcr.request.extlen;
    item *it = ialloc_alloc(&this->ia[state->core], sizeof(item) + totlen, false); // TODO
    if(it) {
        it->refcount = 1;
        uint16_t keylen = state->pkt->mcr.request.keylen;

        //    printf("get_item id: %d, keylen: %ld, totlen: %ld, item: %ld\n",
        //state->pkt->mcr.request.opaque, state->pkt->mcr.request.keylen, totlen, it);
        it->hv = state->hash;
        it->vallen = totlen - keylen;
        it->keylen = keylen;
        memcpy(item_key(it), state->key, totlen);
        state->it = it;
    }

    output switch { case it: out();  else: nothing(); }

        item_unref(state->it);
        output { out(); }
        output { out(%s); }

            (bool x) = inp();
            output { out(x); }

    static __thread int count = 0;
    count++;
    if(count == 32) {
      count = 0;
      clean_log(&this->ia[state->core], state->pkt == NULL);
    }
    }