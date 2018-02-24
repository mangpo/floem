from floem import *
import cache, library


class MyState(State):
    cache_item = Field('citem*')
    hash = Field(Uint(32))


class Mult2(Element):
    def configure(self, *params):
        self.inp = Input(Pointer(Int), Int)
        self.out = Output(Pointer(Int), Int, Int, Pointer(Int))

    def impl(self):
        self.run_c(r'''
        (int* p, int keylen) = inp();
        int x = *p;
        int ans = x*2;
        output { out(p, keylen, keylen, &ans); }
        ''')

class OnlyVal(Element):
    def configure(self):
        self.inp = Input(Pointer(Int), Int, Int, Pointer(Int))
        self.out = Output(Int)

    def impl(self):
        self.run_c(r'''
        (int* p, int keylen, int vallen, int* q) = inp();
        output { out(*q); }
        ''')


class Scalar2Pointer(Element):
    def configure(self):
        self.inp = Input(Int)
        self.out = Output(Pointer(Int), Int)

    def impl(self):
        self.run_c(r'''
        (int x) = inp();
        state->hash = jenkins_hash(&x, sizeof(int));
        output { out(&x, sizeof(int)); }
        ''')


class Scalar2Pointer2(Element):
    def configure(self):
        self.inp = Input(Int, Int)
        self.out = Output(Pointer(Int), Int, Int, Pointer(Int))

    def impl(self):
        self.run_c(r'''
        (int key, int val) = inp();
        state->hash = jenkins_hash(&key, sizeof(int));
        output { out(&key, sizeof(int), sizeof(int), &val); }
        ''')


CacheGet,CacheSet,CacheRelease = cache.cache_default('MyCache', Pointer(Int), [Pointer(Int)],
                                                     hash_value='hash', var_size=True, release_type=[Int])


class MyPipeline(Flow):
    state = PerPacket(MyState)

    def impl(self):
        class compute(CallablePipeline):
            def configure(self):
                self.inp = Input(Int)
                self.out = Output(Int)

            def impl(self):
                cache_get = CacheGet()
                cache_set = CacheSet()
                cache_rel = CacheRelease()
                only_val = OnlyVal()

                self.inp >> Scalar2Pointer() >> cache_get
                cache_get.hit >> only_val
                cache_get.miss >> Mult2() >> cache_set >> only_val
                only_val >> cache_rel >> self.out

        class set(CallablePipeline):
            def configure(self):
                self.inp = Input(Int, Int)

            def impl(self):
                self.inp >> Scalar2Pointer2() >> CacheSet() >> library.Drop()

        compute('compute')
        set('set')


c = Compiler(MyPipeline)
c.testing = "out(compute(11)); out(compute(1)); out(compute(11)); out(compute(1)); set(11, 222); out(compute(11)); out(compute(1));"
c.generate_code_and_run([22,2,22,2, 222, 2])