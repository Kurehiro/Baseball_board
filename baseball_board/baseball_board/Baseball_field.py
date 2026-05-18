#!/usr/bin/env python3

import time
import threading

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor

from std_msgs.msg import Empty
from baseball_board.action import BaseballJudge


class BaseBallFieldServer(Node):
    def __init__(self):
        super().__init__('base_ball_field_server')

        self.callback_group = ReentrantCallbackGroup()
        self.lock = threading.Lock()

        # 球種情報
        self.pitcher_command = None
        self.batter_command = None

        # Enter通知
        self.bat_button_received = False
        self.swing_button_received = False

        # 判定結果
        self.judged = False
        self.pitcher_answer = None
        self.batter_answer = None

        # 両方のAction ClientにResultを返したら次ラウンドに進むためのカウント
        self.result_return_count = 0

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

        # /bat_button を受け取るSubscriber
        self.bat_button_sub = self.create_subscription(
            Empty,
            '/bat_button',
            self.bat_button_callback,
            10
        )

        # /swing_button を受け取るSubscriber
        self.swing_button_sub = self.create_subscription(
            Empty,
            '/swing_button',
            self.swing_button_callback,
            10
        )

        self.get_logger().info('Field Action Server started.')
        self.get_logger().info('pitcher_command, batter_command, /bat_button, /swing_button を待機中です。')

    def bat_button_callback(self, msg):
        with self.lock:
            self.bat_button_received = True
            self.get_logger().info('/bat_button を受信しました。')

    def swing_button_callback(self, msg):
        with self.lock:
            self.swing_button_received = True
            self.get_logger().info('/swing_button を受信しました。')

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

        self.get_logger().info('判定完了。ただし、Result送信は /bat_button と /swing_button の受信後に行います。')

    def is_ready_to_send_result(self):
        """
        Action Resultを返してよい状態か確認する
        """
        return (
            self.judged and
            self.bat_button_received and
            self.swing_button_received
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

        if not self.bat_button_received and not self.swing_button_received:
            return '/bat_button と /swing_button の入力待ちです。'

        if not self.bat_button_received:
            return '/bat_button の入力待ちです。'

        if not self.swing_button_received:
            return '/swing_button の入力待ちです。'

        return '結果送信準備完了です。'

    def reset_round_if_needed(self):
        """
        ピッチャーとバッターの両方にResultを返したら状態をリセットする
        """

        self.result_return_count += 1

        if self.result_return_count >= 2:
            self.get_logger().info('両ClientへResultを返しました。次のラウンドへ移行します。')

            self.pitcher_command = None
            self.batter_command = None

            self.bat_button_received = False
            self.swing_button_received = False

            self.judged = False
            self.pitcher_answer = None
            self.batter_answer = None

            self.result_return_count = 0

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
                    answer = self.pitcher_answer
                    self.reset_round_if_needed()
                    break

                feedback_msg.process = self.make_feedback_text()

            goal_handle.publish_feedback(feedback_msg)
            time.sleep(0.5)

        goal_handle.succeed()

        result = BaseballJudge.Result()
        result.answer = answer

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
                    answer = self.batter_answer
                    self.reset_round_if_needed()
                    break

                feedback_msg.process = self.make_feedback_text()

            goal_handle.publish_feedback(feedback_msg)
            time.sleep(0.5)

        goal_handle.succeed()

        result = BaseballJudge.Result()
        result.answer = answer

        return result


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