main () {

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

            m->mcr.request.magic = PROTOCOL_BINARY_RES;
            m->mcr.request.opcode = PROTOCOL_BINARY_CMD_GET;
            m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
            m->mcr.request.status = PROTOCOL_BINARY_RESPONSE_KEY_ENOENT;

    m->mcr.request.keylen = 0;
    m->mcr.request.extlen = 4;
    m->mcr.request.bodylen = 4;
    *((uint32_t *)m->payload) = 0;

m->mcr.request.magic = PROTOCOL_BINARY_RES;
m->mcr.request.opcode = PROTOCOL_BINARY_CMD_SET;
m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
m->mcr.request.status = %s;

m->mcr.request.keylen = 0;
m->mcr.request.extlen = 0;
m->mcr.request.bodylen = 0;

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
