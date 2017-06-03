from dsl import *


def create_from_net_fixed_size(name, type, max_channels, max_inbuf, port):
    strem_type = "stream_" + name
    Stream = create_state(strem_type, r'''
        int listener;
        int channel[{1}];
        {0} inbuf[{1}][{2}];
        int rest[{1}];
        int nchannels;
        int active;'''.format(type, max_channels, max_inbuf))

    FROM_NET_SAVE = create_element("FROM_NET_SAVE_" + name, [], [Port("out", [])],
            r'''
    fd_set readfds;
    int nfds = this->listener;
    FD_ZERO(&readfds);
    FD_SET(this->listener, &readfds);
    for(int i = 0; i < this->nchannels; i++) {
        FD_SET(this->channel[i], &readfds);
        nfds = (this->channel[i] > nfds)? this->channel[i]: nfds;
    }
    int r = select(nfds + 1, &readfds, NULL, NULL, NULL);

    if(FD_ISSET(this->listener, &readfds)) {
        int channel = accept(this->listener, NULL, NULL);
        assert(channel != -1);
        assert(this->nchannels < %d);
        this->channel[this->nchannels] = channel;
        this->nchannels++;
        printf("new connection!\n");
    }''' % (max_channels)
                                   + r'''

    int active = this->active + 1; // round robin
    for(int k = 0; k < this->nchannels; k++) {
        int i = (k + active) %s this->nchannels;
        int channel = this->channel[i];
        size_t size = sizeof(%s);
        if(FD_ISSET(channel, &readfds)) {
            if(this->rest[i] >= size) {
                int newrest = this->rest[i] %s size;
                memmove(this->inbuf[i], &this->inbuf[i][this->rest[i] / size], newrest);
                this->rest[i] = newrest;
            }
            char *bufp = ((char *) this->inbuf[i]) + this->rest[i];
            ssize_t ret = recv(channel, bufp, MAX_INBUF * size - this->rest[i], 0);
            assert(ret != -1);
            this->rest[i] += ret;
            this->active = i;
            printf("channel %s: receive %s bytes\n", i, ret);
            break;
        }
    }

    output { out(); }
            ''' % ('%', type, '%', '%d', '%ld'),
            None, [(strem_type, "this")])

    FROM_NET_READ = create_element("FROM_NET_READ_" + name, [Port("in", [])], [Port("out", [type + "*"])],
            r'''
    int i = this->active;
    for(int k = 0; k < this->rest[i] / sizeof(%s); k++) {
        out(&this->inbuf[i][k]);
    }
    output multiple;
            ''' % type,
            None, [(strem_type, "this")])

    def compo():
        s = Stream(init=["create_server_socket({0})".format(port), 0, [0], 0, 0, 0])
        from_net_save = FROM_NET_SAVE("from_net_save_" + name, [s])
        from_net_read = FROM_NET_READ("from_net_read_" + name, [s])

        return from_net_read(from_net_save())

    return create_composite_instance("from_net_" + type, compo)


def create_to_net_fixed_size(name, type, hostname, port):
    Sock = create_state("Sock", r'''
        int sock;
        struct sockaddr_in saddr;
        bool connected;''')
    sock = Sock(init=['create_client_socket()', 'create_sockaddr("%s", %d)' % (hostname, port), False])

    TO_NET_SEND = create_element("TO_NET_SEND", [Port("in", [type + "*"])], [],
                                 r'''
                         (%s* t) = in();
                         if(!this->connected) {
                             printf("client try to connect.\n");
                             int r = connect(this->sock, (void *)&this->saddr, sizeof(struct sockaddr_in));
                             assert(r == 0);
                             printf("client connects.\n");
                             this->connected = true;
                         }
                         send(this->sock, t, sizeof(%s), 0);
                         printf("send %s\n", t->x);
                                 ''' % (type, type, '%d'),
                                 None, [("Sock", "this")])
    to_net_send = TO_NET_SEND("to_net_send_" + name, [sock])

    return to_net_send