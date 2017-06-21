import codegen
import desugaring
import graph
import program
import workspace
import pipeline_state
import join_handling


class Compiler:
    def __init__(self, *pipelines):
        self.desugar_mode = "impl"
        self.resource = True
        self.remove_unused = True

        # Extra code
        self.include = None
        self.testing = None
        self.depend = None

        # Compiler option
        self.I = None
        self.pipelines = pipelines

    def generate_graph_from_scope(self, myscope, filename, pktstate=None):
        p = program.Program(*myscope)
        dp = desugaring.desugar(p)

        g = program.program_to_graph_pass(dp, default_process=filename)
        pipeline_state.pipeline_state_pass(g, pktstate)
        join_handling.join_and_resource_annotation_pass(g, self.resource, self.remove_unused)
        return g

    def generate_graph(self, filename="tmp"):
        all = graph.Graph(filename)
        for pipeline in self.pipelines:
            p = pipeline()
            g = self.generate_graph_from_scope(p.scope, filename, p.state)
            all.merge(g)

        g = self.generate_graph_from_scope(workspace.get_last_scope(), filename)
        all.merge(g)
        return all

    def generate_code(self):
        codegen.generate_code(self.generate_graph(), ".c", self.testing, self.include)

    def generate_code_and_run(self, expect=None):
        codegen.generate_code_and_run(self.generate_graph(), self.testing, self.desugar_mode, expect, self.include, self.depend)

    def generate_code_and_compile(self):
        codegen.generate_code_and_compile(self.generate_graph(), self.testing, self.desugar_mode, self.include, self.depend)

    def generate_code_as_header(self, header='tmp'):
        codegen.generate_code_as_header(self.generate_graph(header), self.testing, self.desugar_mode, self.include)

    def compile_and_run(self, name):
        codegen.compile_and_run(name, self.depend)