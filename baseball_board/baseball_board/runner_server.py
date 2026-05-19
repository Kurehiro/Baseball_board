#!/usr/bin/env python3

import time

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer

from baseball_board.action import RunnerSend


class RunnerActionServer(Node):
    def __init__(self):
        super().__init__('runner_action_server')

        self.runner_server = ActionServer(
            self,
            RunnerSend,
            'Runner',
            execute_callback=self.execute_callback
        )

        self.get_logger().info('Runner Action Server started.')
        self.get_logger().info('Action name: Runner')

    def execute_callback(self, goal_handle):
        run_command = goal_handle.request.run_command

        self.get_logger().info(
            f'Runner Goalを受信しました: run_command={run_command}'
        )

        feedback_msg = RunnerSend.Feedback()

        feedback_msg.run_process = 'Runner処理を開始しました。'
        goal_handle.publish_feedback(feedback_msg)
        time.sleep(1.0)

        feedback_msg.run_process = f'{run_command} 塁分の処理を実行中です。'
        goal_handle.publish_feedback(feedback_msg)
        time.sleep(1.0)

        feedback_msg.run_process = 'Runner処理を完了します。'
        goal_handle.publish_feedback(feedback_msg)
        time.sleep(1.0)

        goal_handle.succeed()

        result = RunnerSend.Result()
        result.run_answer = f'Runner処理完了: {run_command}'

        self.get_logger().info(
            f'Runner Resultを返します: {result.run_answer}'
        )

        return result


def main(args=None):
    rclpy.init(args=args)

    node = RunnerActionServer()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('Runner Action Serverを終了します。')
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()