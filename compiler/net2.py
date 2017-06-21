from dsl2 import *
import re


def from_net_fixed_size_instance(name, type, max_channels, max_inbuf, port):
    prefix = name + "_"

    class Stream(State):
        listener = Field(Int)
        channel = Field(Array(Int, max_channels))
        nchannels = Field(Int)
        inbuf = Field(Array(type, [max_channels, max_inbuf]))
        rest = Field(Array(Int, max_channels))
        active = Field(Int)

        def init(self):
            self.listener = "create_server_socket({0})".format(port)
            self.active = 0
            self.nchannels = 0
            self.rest = [0 for i in range(max_channels)]
            self.lock = lambda (x): "init_lock(&%s)" % x

    Stream.__name__ = prefix + Stream.__name__
    type = string_type(type)
    type_star = type + '*'

    stream = Stream()

    class FromNet(Element):
        this = Persistent(Stream)

        def states(self): self.this = stream

        def configure(self): self.out = Output(type_star)

        def impl(self):
            self.run_c(r'''
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
    }''' % (max_channels) +
                       r'''
    int active = this->active + 1; // round robin
    size_t size = sizeof(%s);
    for(int k = 0; k < this->nchannels; k++) {
        int i = (k + active) %s this->nchannels;
        int channel = this->channel[i];
        if(FD_ISSET(channel, &readfds)) {
            if(this->rest[i] >= size) {
                int newrest = this->rest[i] %s size;
                memmove(this->inbuf[i], &this->inbuf[i][this->rest[i] / size], newrest);
                this->rest[i] = newrest;
            }
            char *bufp = ((char *) this->inbuf[i]) + this->rest[i];
            ssize_t ret = recv(channel, bufp, (size * %d) - this->rest[i], 0);
            assert(ret != -1);
            this->rest[i] += ret;
            this->active = i;
            printf("channel %s: receive %s bytes\n", i, ret);
            break;
        }
    }
    ''' % (type, '%', '%', max_inbuf, '%d', '%ld') +
                       r'''
    int i = this->active;
    for(int k = 0; k < this->rest[i] / size; k++) {
        out(&this->inbuf[i][k]);
    }
    if(this->rest[i] >= size) {
        int newrest = this->rest[i] % size;
        memmove(this->inbuf[i], &this->inbuf[i][this->rest[i] / size], newrest);
        this->rest[i] = newrest;
    }
    output multiple;
    ''')

    FromNet.__name__ = prefix + FromNet.__name__

    return FromNet(prefix + "_from_net")


class Socket(State):
    sock = Field(Int)
    saddr = Field('struct sockaddr_in')
    connected = Field(Bool)

    def init(self, hostname=None, port=None):
        if hostname and port:
            self.saddr = 'create_sockaddr({0}, {1})'.format(hostname,port)
        self.sock = 'create_client_socket()'
        self.connected = False


def to_net_fixed_size_instance(name, type, hostname, port):
    m = re.match('[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+', hostname)
    if m:
        hostname = '"%s"' % hostname
    sock = Socket(init=[hostname, port])

    type = string_type(type)
    type_star = type + '*'

    class ToNet(Element):
        this = Persistent(Socket)

        def configure(self): self.inp = Input(type_star)

        def states(self): self.this = sock

        def impl(self):
            self.run_c(r'''
            (%s* t) = inp();
            if(!this->connected) {
                printf("client try to connect.\n");
                int r = connect(this->sock, (void *)&this->saddr, sizeof(struct sockaddr_in));
                while(r != 0) {
                    sleep(1);
                    r = connect(this->sock, (void *)&this->saddr, sizeof(struct sockaddr_in));
                }
                printf("client connects.\n");
                this->connected = true;
                }
            send(this->sock, t, sizeof(%s), 0);
            ''' % (type, type))

    return ToNet(name + "_to_net")