#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from std_msgs.msg import Empty
from baseball_board.action import BaseballJudge


class PitcherActionClient(Node):

    def __init__(self):
        super().__init__('pitcher_action_client')

        # ==========================
        # Action Client
        # ==========================
        self._action_client = ActionClient(
            self,
            BaseballJudge,
            'pitcher_command'
        )

        # ==========================
        # restart subscriber
        # ==========================
        self.restart_sub = self.create_subscription(
            Empty,
            '/restart',
            self.restart_callback,
            10
        )

        # ==========================
        # 状態管理
        # ==========================
        self.game_running = False
        self.restart_pending = False

        # 初回ゲーム開始
        self.start_game()

    # ==================================================
    # restart callback
    # ==================================================
    def restart_callback(self, msg):

        if self.game_running:

            self.get_logger().info(
                '試合中なので restart を保留します'
            )

            self.restart_pending = True

            return

        self.get_logger().info(
            'restart受信 -> 次試合開始'
        )

        self.start_game()

    # ==================================================
    # 試合開始
    # ==================================================
    def start_game(self):

        self.game_running = True

        pitch_type = input(
            '球種を入力してください: '
        )

        goal_msg = BaseballJudge.Goal()
        goal_msg.command = pitch_type

        self.get_logger().info(
            f'球種送信: {pitch_type}'
        )

        self._action_client.wait_for_server()

        future = self._action_client.send_goal_async(
            goal_msg,
            feedback_callback=self.feedback_callback
        )

        future.add_done_callback(
            self.goal_response_callback
        )

    # ==================================================
    # feedback
    # ==================================================
    def feedback_callback(self, feedback_msg):

        feedback = feedback_msg.feedback

        self.get_logger().info(
            f'フィードバック: {feedback.process}'
        )

    # ==================================================
    # goal response
    # ==================================================
    def goal_response_callback(self, future):

        goal_handle = future.result()

        if not goal_handle.accepted:

            self.get_logger().info(
                'ゴール拒否'
            )

            self.game_running = False
            return

        self.get_logger().info(
            '投球開始'
        )

        result_future = goal_handle.get_result_async()

        result_future.add_done_callback(
            self.result_callback
        )

    # ==================================================
    # result
    # ==================================================
    def result_callback(self, future):

        result = future.result().result

        self.get_logger().info(
            f'結果: {result.answer}'
        )

        self.game_running = False

        if self.restart_pending:

            self.get_logger().info(
                '保留していた restart を処理します'
            )

            self.restart_pending = False

            self.start_game()

        else:

            self.get_logger().info(
                '/restart 待機中...'
            )


# ==================================================
# main
# ==================================================
def main():

    rclpy.init()

    node = PitcherActionClient()

    rclpy.spin(node)

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()