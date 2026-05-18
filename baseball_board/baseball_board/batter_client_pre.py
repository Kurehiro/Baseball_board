#!/usr/bin/env python3

import time

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from std_msgs.msg import Empty
from baseball_board.action import BaseballJudge


class BatterClient(Node):
    def __init__(self):
        super().__init__('batter_client')

        self.action_client = ActionClient(
            self,
            BaseballJudge,
            'batter_command'
        )

        self.button_pub = self.create_publisher(
            Empty,
            '/swing_button',
            10
        )

    def send_goal(self):
        goal_msg = BaseballJudge.Goal()
        goal_msg.command = 'straight'

        self.get_logger().info('バッター: straight を送信します')
        self.get_logger().info('Field Serverを待機中...')

        self.action_client.wait_for_server()

        return self.action_client.send_goal_async(
            goal_msg,
            feedback_callback=self.feedback_callback
        )

    def feedback_callback(self, feedback_msg):
        feedback = feedback_msg.feedback
        self.get_logger().info(f'Feedback: {feedback.process}')

    def publish_button(self):
        msg = Empty()

        # Topic通信の取りこぼし防止用に少し待って複数回送る
        time.sleep(0.5)

        for _ in range(3):
            self.button_pub.publish(msg)
            self.get_logger().info('/swing_button を送信しました')
            time.sleep(0.2)


def main(args=None):
    rclpy.init(args=args)

    node = BatterClient()

    goal_future = node.send_goal()
    rclpy.spin_until_future_complete(node, goal_future)

    goal_handle = goal_future.result()

    if not goal_handle.accepted:
        node.get_logger().info('Goalが拒否されました')
        node.destroy_node()
        rclpy.shutdown()
        return

    node.get_logger().info('Goalが受理されました')

    node.publish_button()

    result_future = goal_handle.get_result_async()
    rclpy.spin_until_future_complete(node, result_future)

    result = result_future.result().result
    node.get_logger().info(f'バッター側の結果: {result.answer}')

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()