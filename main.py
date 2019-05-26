import numpy as np
import random
from vprtw_aco_figure import VrptwAcoFigure
from vrptw_base import VrptwGraph
from ant import Ant


class VrptwAco:
    def __init__(self, graph: VrptwGraph, ants_num=10, max_iter=200, alpha=1, beta=2):
        super()
        # graph 结点的位置、服务时间信息
        self.graph = graph
        # ants_num 蚂蚁数量
        self.ants_num = ants_num
        # max_iter 最大迭代次数
        self.max_iter = max_iter
        # vehicle_capacity 表示每辆车的最大载重
        self.max_load = graph.vehicle_capacity
        # 信息素强度
        self.Q = 1
        # alpha 信息素信息重要新
        self.alpha = alpha
        # beta 启发性信息重要性
        self.beta = beta
        # q0 表示直接选择概率最大的下一点的概率
        self.q0 = 0.1
        # best path
        self.best_path_distance = None
        self.best_path = None

        self.whether_or_not_to_show_figure = False

        if self.whether_or_not_to_show_figure:
            # figure
            self.figure = VrptwAcoFigure(self.graph)

    def run(self):
        """
        运行蚁群优化算法
        :return:
        """
        # 最大迭代次数
        for iter in range(self.max_iter):

            # 为每只蚂蚁设置当前车辆负载，当前旅行距离，当前时间
            ants = list(Ant(self.graph) for _ in range(self.ants_num))
            for k in range(self.ants_num):

                # 蚂蚁需要访问完所有的客户
                while not ants[k].index_to_visit_empty():
                    next_index = self.select_next_index(ants[k])
                    # 判断加入该位置后，是否还满足约束条件, 如果不满足，则再选择一次，然后再进行判断
                    if not ants[k].check_condition(next_index):
                        next_index = self.select_next_index(ants[k])
                        if not ants[k].check_condition(next_index):
                            next_index = 0

                    # 更新蚂蚁路径
                    ants[k].move_to_next_index(next_index)
                    self.graph.local_update_pheromone(ants[k].current_index, next_index)

                # 最终回到0位置
                ants[k].move_to_next_index(0)
                self.graph.local_update_pheromone(ants[k].current_index, 0)

            # 计算所有蚂蚁的路径长度
            paths_distance = np.array([ant.total_travel_distance for ant in ants])

            # 记录当前的最佳路径
            best_index = np.argmin(paths_distance)
            if self.best_path is None:
                self.best_path = ants[int(best_index)].travel_path
                self.best_path_distance = paths_distance[best_index]
                if self.whether_or_not_to_show_figure:
                    self.figure.init_figure(self.best_path)

            elif paths_distance[best_index] < self.best_path_distance:
                self.best_path = ants[int(best_index)].travel_path
                self.best_path_distance = paths_distance[best_index]
                if self.whether_or_not_to_show_figure:
                    self.figure.update_figure(self.best_path)

            print('[iteration %d]: best distance %f' % (iter, self.best_path_distance))
            # 更新信息素表
            self.graph.global_update_pheromone(self.best_path, self.best_path_distance)

    def select_next_index(self, ant):
        """
        选择下一个结点
        :param ant:
        :return:
        """
        current_index = ant.current_index
        index_to_visit = ant.index_to_visit

        transition_prob = np.power(self.graph.pheromone_mat[current_index][index_to_visit], self.alpha) * \
            np.power(self.graph.heuristic_info_mat[current_index][index_to_visit], self.beta)

        if np.random.rand() < self.q0:
            max_prob_index = np.argmax(transition_prob)
            next_index = index_to_visit[max_prob_index]
        else:
            # 使用轮盘赌算法
            next_index = self.stochastic_accept(index_to_visit, transition_prob)
        return next_index

    def stochastic_accept(self, index_to_visit, transition_prob):
        """
        轮盘赌
        :param index_to_visit: a list of N index (list or tuple)
        :param transition_prob:
        :return: selected index
        """
        # calculate N and max fitness value
        N = len(index_to_visit)

        # normalize
        sum_tran_prob = np.sum(transition_prob)
        norm_transition_prob = transition_prob/sum_tran_prob

        # select: O(1)
        while True:
            # randomly select an individual with uniform probability
            ind = int(N * random.random())
            if random.random() <= norm_transition_prob[ind]:
                return index_to_visit[ind]

    def new_active_ant(self, ant: Ant, local_search: bool, IN):

        # 计算从当前位置可以达到的下一个位置
        next_index_meet_constrains = ant.cal_next_index_meet_constrains()
        while len(next_index_meet_constrains) > 0:
            index_num = len(next_index_meet_constrains)
            ready_time = np.zeros(index_num)
            due_time = np.zeros(index_num)
            for i in range(index_num):
                ready_time[i] = ant.graph.nodes[next_index_meet_constrains[i]].ready_time
                due_time[i] = ant.graph.nodes[next_index_meet_constrains[i]].due_time

            delivery_time = np.max(ant.vehicle_travel_time + ant.graph.node_dist_mat[ant.current_index][next_index_meet_constrains], ready_time)
            delat_time = delivery_time - ant.vehicle_travel_time
            distance = delat_time * (due_time - ant.vehicle_travel_time)
            distance = np.max(1.0, distance-IN)

            closeness = 1/distance

            # 按照概率选择下一个点next_index
            if np.random.rand() < ant.graph.q0:
                max_prob_index = np.argmax(closeness)
                next_index = next_index_meet_constrains[max_prob_index]
            else:
                # 使用轮盘赌算法
                next_index = ant.graph.stochastic_accept(next_index_meet_constrains, closeness)
            ant.move_to_next_index(next_index)

            # 更新信息素矩阵

            # 重新计算可选的下一个点
            next_index_meet_constrains = ant.cal_next_index_meet_constrains()

        ant.insertion_procedure()

        # ant.index_to_visit_empty()==True就是feasible的意思
        if local_search is True and ant.index_to_visit_empty():
            new_path = ant.local_search_procedure()
            if new_path is not None:
                pass

    def acs_time(self, vehicle_num):
        # how to calculate init_pheromone_val
        new_graph = self.graph.construct_graph_with_duplicated_depot(vehicle_num, 1)

        # 初始化信息素矩阵
        while True:
            for k in range(self.ants_num):
                ant = Ant(new_graph, random.randint(0, vehicle_num-1))
                self.new_active_ant(ant, True, 0)
                # if ant.index_to_visit_empty() and ant.total_travel_distance < global_travel_distance:
                    # send ant.travel_path
                    # pass


if __name__ == '__main__':
    file_path = './solomon-100/c101.txt'
    graph = VrptwGraph(file_path)

    vrptw = VrptwAco(graph)
    vrptw.run()
