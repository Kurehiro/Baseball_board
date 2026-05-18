#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from std_msgs.msg import Empty
from baseball_board.action import BaseballJudge


class BatterActionClient(Node):

    def __init__(self):
        super().__init__('batter_action_client')

        self._action_client = ActionClient(
            self,
            BaseballJudge,
            'batter_command'
        )

        self.enter_pub = self.create_publisher(
            Empty,
            '/swing_button',
            10
        )

    def send_goal(self, expected_pitch):
        goal_msg = BaseballJudge.Goal()
        goal_msg.command = expected_pitch

        self.get_logger().info(
            f'待ち球種送信: {expected_pitch}'
        )

        self._action_client.wait_for_server()

        return self._action_client.send_goal_async(
            goal_msg,
            feedback_callback=self.feedback_callback
        )

    def feedback_callback(self, feedback_msg):
        feedback = feedback_msg.feedback

        self.get_logger().info(
            f'フィードバック: {feedback.process}'
        )

    def send_swing_button(self):
        msg = Empty()
        self.enter_pub.publish(msg)

        self.get_logger().info(
            '/swing_button を送信しました'
        )


def main():
    rclpy.init()

    batter_client = BatterActionClient()

    expected_pitch = input(
        '待つ球種を入力してください: '
    )

    future = batter_client.send_goal(expected_pitch)

    rclpy.spin_until_future_complete(
        batter_client,
        future
    )

    goal_handle = future.result()

    if not goal_handle.accepted:
        batter_client.get_logger().info(
            'ゴール拒否'
        )

    else:
        batter_client.get_logger().info(
            '打席開始'
        )

        input('Enterキーを押すと /swing_button を送信します: ')
        batter_client.send_swing_button()

        result_future = goal_handle.get_result_async()

        rclpy.spin_until_future_complete(
            batter_client,
            result_future
        )

        result = result_future.result().result

        batter_client.get_logger().info(
            f'結果: {result.answer}'
        )

    batter_client.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()