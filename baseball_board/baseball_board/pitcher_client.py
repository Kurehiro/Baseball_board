#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from std_msgs.msg import Empty
from baseball_board.action import BaseballJudge

class PitcherActionClient(Node):
 
    def __init__(self):
 
        super().__init__('pitcher_action_client')
 
        # Action Client
        self._action_client = ActionClient(
            self,
            BaseballJudge,
            'pitcher_command'
        )
 
        # Enter通知用Publisher
        self.enter_pub = self.create_publisher(
            Empty,
            '/bat_button',
            10
        )
 
    def send_goal(self, pitch_type):
 
        goal_msg = BaseballJudge.Goal()
        goal_msg.command = pitch_type
 
        self.get_logger().info(
            f'球種送信: {pitch_type}'
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
 
        # Enter待機
        input('Enterキーを押してください')
 
        # Enter通知送信
        msg = Empty()
 
        self.enter_pub.publish(msg)
 
        self.get_logger().info('/bat_button を送信しました')
 
def main():
 
    rclpy.init()
 
    pitcher_client = PitcherActionClient()
 
    pitch_type = input(
        '球種を入力してください: '
    )
 
    future = pitcher_client.send_goal(
        pitch_type
    )
 
    rclpy.spin_until_future_complete(
        pitcher_client,
        future
    )
 
    goal_handle = future.result()
 
    if not goal_handle.accepted:
 
        pitcher_client.get_logger().info(
            'ゴール拒否'
        )
 
    else:
 
        pitcher_client.get_logger().info(
            '投球開始'
        )
 
        result_future = goal_handle.get_result_async()
 
        rclpy.spin_until_future_complete(
            pitcher_client,
            result_future
        )
 
        result = result_future.result().result
 
        pitcher_client.get_logger().info(
            f'結果: {result.answer}'
        )
 
    pitcher_client.destroy_node()
 
    rclpy.shutdown()
 
if __name__ == '__main__':
    main()
 