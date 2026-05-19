#!/usr/bin/env python3

import time
import threading
import random

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor

from std_msgs.msg import Empty
from baseball_board.action import BaseballJudge
from baseball_board.action import RunnerSend


class BaseBallFieldServer(Node):
    def __init__(self):
        super().__init__('base_ball_field_server')

        self.callback_group = ReentrantCallbackGroup()
        self.lock = threading.Lock()

        # 球種情報
        self.pitcher_command = None
        self.batter_command = None

        # 判定結果
        self.judged = False
        self.pitcher_answer = None
        self.batter_answer = None

        self.run_check = False

        # 両方のAction ClientにResultを返したら次ラウンドに進むためのカウント
        self.result_return_count = 0

        # Runner Serverへ送るAction Client
        self.runner_client = ActionClient(
            self,
            RunnerSend,
            'Runner',
            callback_group=self.callback_group
        )

        # Runner ServerのResult受信後に送るrestart topic
        self.restart_pub = self.create_publisher(
            Empty,
            '/restart',
            10
        )

        # Runner Actionの状態管理
        self.runner_started = False
        self.runner_done = False
        self.runner_answer = None
        self.restart_sent = False

        # ピッチャー側から球種を受け取るAction Server
        self.pitcher_server = ActionServer(
            self,
            BaseballJudge,
            'pitcher_command',
            execute_callback=self.pitcher_callback,
            callback_group=self.callback_group
        )

        # バッター側から球種を受け取るAction Server
        self.batter_server = ActionServer(
            self,
            BaseballJudge,
            'batter_command',
            execute_callback=self.batter_callback,
            callback_group=self.callback_group
        )


        self.get_logger().info('Field Action Server started.')
        self.get_logger().info('pitcher_command, batter_commandを待機中です。')

    def judge(self):
        """
        ピッチャーとバッターの球種がそろったら判定する
        """

        if self.pitcher_command is None:
            return

        if self.batter_command is None:
            return

        if self.judged:
            return

        self.get_logger().info(
            f'判定処理開始: pitcher={self.pitcher_command}, batter={self.batter_command}'
        )

        if self.pitcher_command == self.batter_command:
            self.batter_answer = 'Hit: 打った'
            self.pitcher_answer = 'Hit: 打たれた'
        else:
            self.batter_answer = 'Miss: 打てなかった'
            self.pitcher_answer = 'Safe: 打たれなかった'

        self.judged = True

        self.get_logger().info('判定完了。Action Result送信処理へ進みます。')

    def is_ready_to_send_result(self):
        """
        Action Resultを返してよい状態か確認する
        """
        return (
            self.judged
        )

    def make_feedback_text(self):
        """
        現在の待機状態をFeedback用の文字列にする
        """

        if self.pitcher_command is None:
            return 'ピッチャーの球種入力待ちです。'

        if self.batter_command is None:
            return 'バッターの球種入力待ちです。'

        if not self.judged:
            return '判定処理中です。'

        return '結果送信準備完了です。'

    def reset_round_if_needed(self):
        """
        ピッチャーとバッターの両方にResultを返したら状態をリセットする
        """

        self.result_return_count += 1

        if self.result_return_count >= 2:
            self.get_logger().info('両ClientへResultを返しました。次のラウンドへ移行します。')

            # HitでもMissでも、次ラウンド開始用にrestartを送る
            self.publish_restart()

            self.pitcher_command = None
            self.batter_command = None

            self.judged = False
            self.pitcher_answer = None
            self.batter_answer = None

            self.runner_started = False
            self.runner_done = False
            self.runner_answer = None

            self.result_return_count = 0
            self.restart_sent = False


    def pitcher_callback(self, goal_handle):
        """
        ピッチャー側Actionの処理
        """

        command = goal_handle.request.command

        with self.lock:
            self.pitcher_command = command
            self.get_logger().info(f'ピッチャー球種を受信: {command}')
            self.judge()

        feedback_msg = BaseballJudge.Feedback()

        while rclpy.ok():
            with self.lock:
                if self.is_ready_to_send_result():
                    pitcher_result_answer = self.pitcher_answer
                    hit_flag = self.batter_answer == 'Hit: 打った'
                    break

                feedback_msg.process = self.make_feedback_text()

            goal_handle.publish_feedback(feedback_msg)
            time.sleep(0.5)

        if hit_flag:
            self.call_runner_server_if_hit(goal_handle, feedback_msg)

        goal_handle.succeed()

        result = BaseballJudge.Result()
        result.answer = pitcher_result_answer

        self.reset_round_if_needed()

        return result

    def batter_callback(self, goal_handle):
        """
        バッター側Actionの処理
        """

        command = goal_handle.request.command

        with self.lock:
            self.batter_command = command
            self.get_logger().info(f'バッター球種を受信: {command}')
            self.judge()

        feedback_msg = BaseballJudge.Feedback()

        while rclpy.ok():
            with self.lock:
                if self.is_ready_to_send_result():
                    batter_result_answer = self.batter_answer
                    hit_flag = self.batter_answer == 'Hit: 打った'
                    break

                feedback_msg.process = self.make_feedback_text()

            goal_handle.publish_feedback(feedback_msg)
            time.sleep(0.5)

        if hit_flag:
            self.call_runner_server_if_hit(goal_handle, feedback_msg)

        goal_handle.succeed()

        result = BaseballJudge.Result()
        result.answer = batter_result_answer

        self.reset_round_if_needed()

        return result

    def runner_feedback_callback(self, feedback_msg):
        feedback = feedback_msg.feedback
        self.get_logger().info(
            f'Runner Feedback: {feedback.run_process}'
        )

    def publish_restart(self):
        if self.restart_sent:
            return

        self.restart_sent = True

        msg = Empty()
        self.restart_pub.publish(msg)
        self.get_logger().info('/restart を送信しました。')

    def call_runner_server_if_hit(self, goal_handle, feedback_msg):
        """
        Hit時だけRunner Serverへ1〜3のランダム数字を送る。
        Runner ServerからResultを受け取ったら /restart を送る。
        ピッチャー・バッター側Actionには、待機中Feedbackだけ出す。
        """

        with self.lock:
            if self.batter_answer != 'Hit: 打った':
                return

            if self.runner_done:
                return

            if self.runner_started:
                is_sender = False
            else:
                self.runner_started = True
                is_sender = True

        # もう片方のcallbackがRunner通信を開始している場合は、完了を待つだけ
        if not is_sender:
            while rclpy.ok():
                with self.lock:
                    if self.runner_done:
                        return

                feedback_msg.process = 'Runner ServerのResult待ちです。'
                goal_handle.publish_feedback(feedback_msg)
                time.sleep(0.5)

            return

        # 1〜3をランダム送信
        base_number = random.randint(1, 3)

        run_goal = RunnerSend.Goal()
        run_goal.run_command = str(base_number)

        self.get_logger().info(
            f'Runner ServerへGoal送信: {run_goal.run_command}'
        )

        while not self.runner_client.wait_for_server(timeout_sec=1.0):
            feedback_msg.process = 'Runner Action Serverの起動待ちです。'
            goal_handle.publish_feedback(feedback_msg)
            self.get_logger().info('Runner Action Serverを待機中です。')

        send_goal_future = self.runner_client.send_goal_async(
            run_goal,
            feedback_callback=self.runner_feedback_callback
        )

        while rclpy.ok() and not send_goal_future.done():
            feedback_msg.process = 'Runner ServerへGoal送信中です。'
            goal_handle.publish_feedback(feedback_msg)
            time.sleep(0.5)

        runner_goal_handle = send_goal_future.result()

        if not runner_goal_handle.accepted:
            self.get_logger().info('Runner Goalが拒否されました。')

            with self.lock:
                self.runner_answer = 'Runner Goal rejected'
                self.runner_done = True
                self.runner_started = False

            return

        self.get_logger().info('Runner Goalが受理されました。')

        result_future = runner_goal_handle.get_result_async()

        while rclpy.ok() and not result_future.done():
            feedback_msg.process = 'Runner ServerのResult待ちです。'
            goal_handle.publish_feedback(feedback_msg)
            time.sleep(0.5)

        runner_result = result_future.result().result

        self.get_logger().info(
            f'Runner Result: {runner_result.run_answer}'
        )

        self.publish_restart()

        with self.lock:
            self.runner_answer = runner_result.run_answer
            self.runner_done = True
            self.runner_started = False

def main(args=None):
    rclpy.init(args=args)

    node = BaseBallFieldServer()

    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)

    try:
        executor.spin()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()