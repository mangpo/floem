from dsl import *



@composite_instance
def compo(): pass
my_compo = compo()

# --->
def compo(): pass
my_compo = create_composite_instance("_", compo)


@composite_instance_at(t)
def compo():
    t.run(a)
    t.start(a)
my_compo = compo()

# --->
def compo():
    t.run(a)
    t.start(a)
my_compo = create_composite_instance("_", compo)
#
my_compo = create_composite("compo_name", compo)
my_compo_instance = my_compo("inst_name")
# TODO
# - collect all instances created inside compo, t.run(compo_inst)
# - t.run, t.start inside compo(t)
# - t.run, t.start inside compo()@composite_instance_at(t)
