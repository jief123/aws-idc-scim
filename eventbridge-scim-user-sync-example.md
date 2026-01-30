# EventBridge 监听 SCIM 用户同步触发 Lambda

## ✅ 可行性确认

**是的，EventBridge 可以监听 SCIM 同步的用户创建事件！**

根据 AWS 官方文档：
- [EventBridge Integration](https://docs.aws.amazon.com/singlesignon/latest/userguide/eventbridge-integration.html)
- [SCIM Logging with CloudTrail](https://docs.aws.amazon.com/singlesignon/latest/userguide/scim-logging-using-cloudtrail.html)

IAM Identity Center 的 SCIM API 调用会记录到 CloudTrail，EventBridge 可以监听这些事件并触发自动化工作流。

---

## 📋 支持的 SCIM 事件

EventBridge 可以监听以下 SCIM 操作：

| 事件名称 | 说明 | Event Source |
|---------|------|--------------|
| `CreateUser` | 创建新用户 | `identitystore-scim.amazonaws.com` |
| `DeleteUser` | 删除用户 | `identitystore-scim.amazonaws.com` |
| `PatchUser` | 更新用户信息 | `identitystore-scim.amazonaws.com` |
| `PutUser` | 替换用户信息 | `identitystore-scim.amazonaws.com` |
| `CreateGroup` | 创建新组 | `identitystore-scim.amazonaws.com` |
| `DeleteGroup` | 删除组 | `identitystore-scim.amazonaws.com` |
| `PatchGroup` | 更新组信息 | `identitystore-scim.amazonaws.com` |

---

## 🏗️ 架构设计

```
IdP (Okta/Azure AD/Google)
    ↓ SCIM Sync
IAM Identity Center
    ↓ CloudTrail Event
EventBridge Rule
    ↓ Trigger
Lambda Function
    ↓ Process
Your Custom Logic (通知/审计/自动化)
```

---

## 📝 EventBridge 规则示例

### 1. 监听用户创建事件

```json
{
  "source": ["aws.cloudtrail"],
  "detail-type": ["AWS API Call via CloudTrail"],
  "detail": {
    "eventSource": ["identitystore-scim.amazonaws.com"],
    "eventName": ["CreateUser"]
  }
}
```

### 2. 监听用户创建和更新事件

```json
{
  "source": ["aws.cloudtrail"],
  "detail-type": ["AWS API Call via CloudTrail"],
  "detail": {
    "eventSource": ["identitystore-scim.amazonaws.com"],
    "eventName": ["CreateUser", "PatchUser", "PutUser"]
  }
}
```

### 3. 监听所有 SCIM 用户操作

```json
{
  "source": ["aws.cloudtrail"],
  "detail-type": ["AWS API Call via CloudTrail"],
  "detail": {
    "eventSource": ["identitystore-scim.amazonaws.com"],
    "eventName": [
      {
        "prefix": "CreateUser"
      },
      {
        "prefix": "PatchUser"
      },
      {
        "prefix": "DeleteUser"
      }
    ]
  }
}
```

---

## 🔧 CloudFormation 模板示例

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: EventBridge Rule to trigger Lambda on SCIM user sync

Resources:
  # Lambda 函数
  SCIMUserSyncHandler:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: scim-user-sync-handler
      Runtime: python3.12
      Handler: index.lambda_handler
      Role: !GetAtt LambdaExecutionRole.Arn
      Code:
        ZipFile: |
          import json
          import boto3
          
          def lambda_handler(event, context):
              print("Received SCIM event:", json.dumps(event, indent=2))
              
              # 提取事件信息
              detail = event.get('detail', {})
              event_name = detail.get('eventName')
              event_time = detail.get('eventTime')
              
              # 提取用户信息
              response_elements = detail.get('responseElements', {})
              user_id = response_elements.get('id')
              user_name = response_elements.get('userName', 'HIDDEN')
              display_name = response_elements.get('displayName', 'HIDDEN')
              
              print(f"Event: {event_name}")
              print(f"Time: {event_time}")
              print(f"User ID: {user_id}")
              print(f"User Name: {user_name}")
              print(f"Display Name: {display_name}")
              
              # 在这里添加你的自定义逻辑
              # 例如：
              # - 发送通知到 SNS/Slack
              # - 写入审计日志到 DynamoDB
              # - 触发其他自动化流程
              # - 同步到其他系统
              
              return {
                  'statusCode': 200,
                  'body': json.dumps({
                      'message': 'SCIM event processed successfully',
                      'eventName': event_name,
                      'userId': user_id
                  })
              }

  # Lambda 执行角色
  LambdaExecutionRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: lambda.amazonaws.com
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
      Policies:
        - PolicyName: IdentityStoreReadAccess
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - identitystore:DescribeUser
                  - identitystore:ListUsers
                  - identitystore:DescribeGroup
                  - identitystore:ListGroups
                Resource: '*'

  # EventBridge 规则
  SCIMUserCreateRule:
    Type: AWS::Events::Rule
    Properties:
      Name: scim-user-create-rule
      Description: Trigger Lambda when SCIM creates a new user
      State: ENABLED
      EventPattern:
        source:
          - aws.cloudtrail
        detail-type:
          - AWS API Call via CloudTrail
        detail:
          eventSource:
            - identitystore-scim.amazonaws.com
          eventName:
            - CreateUser
      Targets:
        - Arn: !GetAtt SCIMUserSyncHandler.Arn
          Id: SCIMUserSyncHandlerTarget

  # Lambda 权限
  LambdaInvokePermission:
    Type: AWS::Lambda::Permission
    Properties:
      FunctionName: !Ref SCIMUserSyncHandler
      Action: lambda:InvokeFunction
      Principal: events.amazonaws.com
      SourceArn: !GetAtt SCIMUserCreateRule.Arn

Outputs:
  LambdaFunctionArn:
    Description: Lambda Function ARN
    Value: !GetAtt SCIMUserSyncHandler.Arn
  
  EventBridgeRuleArn:
    Description: EventBridge Rule ARN
    Value: !GetAtt SCIMUserCreateRule.Arn
```

---

## 📊 CloudTrail 事件示例

### 成功的 CreateUser 事件

```json
{
  "eventVersion": "1.10",
  "userIdentity": {
    "type": "WebIdentityUser",
    "accountId": "123456789012",
    "accessKeyId": "xxxx"
  },
  "eventTime": "2026-01-21T07:00:00Z",
  "eventSource": "identitystore-scim.amazonaws.com",
  "eventName": "CreateUser",
  "awsRegion": "us-east-1",
  "sourceIPAddress": "203.0.113.0",
  "userAgent": "Go-http-client/2.0",
  "requestParameters": {
    "httpBody": {
      "displayName": "HIDDEN_DUE_TO_SECURITY_REASONS",
      "schemas": [
        "urn:ietf:params:scim:schemas:core:2.0:User"
      ],
      "name": {
        "familyName": "HIDDEN_DUE_TO_SECURITY_REASONS",
        "givenName": "HIDDEN_DUE_TO_SECURITY_REASONS"
      },
      "active": true,
      "userName": "HIDDEN_DUE_TO_SECURITY_REASONS"
    },
    "tenantId": "xxxx"
  },
  "responseElements": {
    "meta": {
      "created": "Jan 21, 2026, 7:00:00 AM",
      "lastModified": "Jan 21, 2026, 7:00:00 AM",
      "resourceType": "User"
    },
    "displayName": "HIDDEN_DUE_TO_SECURITY_REASONS",
    "schemas": [
      "urn:ietf:params:scim:schemas:core:2.0:User"
    ],
    "name": {
      "familyName": "HIDDEN_DUE_TO_SECURITY_REASONS",
      "givenName": "HIDDEN_DUE_TO_SECURITY_REASONS"
    },
    "active": true,
    "id": "c4488478-a0e1-700e-3d75-96c6bb641596",
    "userName": "HIDDEN_DUE_TO_SECURITY_REASONS"
  },
  "requestID": "xxxx",
  "eventID": "xxxx",
  "readOnly": false,
  "eventType": "AwsApiCall",
  "managementEvent": true,
  "recipientAccountId": "123456789012",
  "eventCategory": "Management",
  "tlsDetails": {
    "clientProvidedHostHeader": "scim.us-east-1.amazonaws.com"
  }
}
```

---

## 🚀 部署步骤

### 1. 确保 CloudTrail 已启用

```bash
# 检查 CloudTrail 状态
aws cloudtrail get-trail-status --name <trail-name>

# 如果需要，创建新的 Trail
aws cloudtrail create-trail \
  --name scim-events-trail \
  --s3-bucket-name <your-bucket-name>

aws cloudtrail start-logging --name scim-events-trail
```

### 2. 部署 CloudFormation 模板

```bash
aws cloudformation create-stack \
  --stack-name scim-eventbridge-lambda \
  --template-body file://eventbridge-scim-rule.yaml \
  --capabilities CAPABILITY_IAM \
  --region us-east-1
```

### 3. 测试事件触发

从你的 IdP (Okta/Azure AD/Google) 创建一个新用户，触发 SCIM 同步。

### 4. 查看 Lambda 日志

```bash
aws logs tail /aws/lambda/scim-user-sync-handler --follow
```

---

## 🔍 高级用例

### 1. 发送 Slack 通知

```python
import json
import urllib3

def lambda_handler(event, context):
    detail = event.get('detail', {})
    event_name = detail.get('eventName')
    response_elements = detail.get('responseElements', {})
    user_id = response_elements.get('id')
    
    # 发送到 Slack
    http = urllib3.PoolManager()
    slack_webhook = 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
    
    message = {
        "text": f"🆕 New user created via SCIM sync",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Event:* {event_name}\n*User ID:* {user_id}"
                }
            }
        ]
    }
    
    http.request('POST', slack_webhook, 
                 body=json.dumps(message),
                 headers={'Content-Type': 'application/json'})
    
    return {'statusCode': 200}
```

### 2. 写入审计日志到 DynamoDB

```python
import boto3
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('scim-audit-log')

def lambda_handler(event, context):
    detail = event.get('detail', {})
    
    # 写入审计日志
    table.put_item(
        Item={
            'eventId': detail.get('eventID'),
            'timestamp': detail.get('eventTime'),
            'eventName': detail.get('eventName'),
            'userId': detail.get('responseElements', {}).get('id'),
            'sourceIP': detail.get('sourceIPAddress'),
            'userAgent': detail.get('userAgent'),
            'fullEvent': json.dumps(event)
        }
    )
    
    return {'statusCode': 200}
```

### 3. 同步到外部系统

```python
import boto3
import requests

def lambda_handler(event, context):
    detail = event.get('detail', {})
    response_elements = detail.get('responseElements', {})
    
    user_id = response_elements.get('id')
    
    # 获取完整用户信息
    identitystore = boto3.client('identitystore')
    identity_store_id = 'd-90661de33f'  # 你的 Identity Store ID
    
    try:
        user = identitystore.describe_user(
            IdentityStoreId=identity_store_id,
            UserId=user_id
        )
        
        # 同步到外部系统
        external_api_url = 'https://your-system.com/api/users'
        requests.post(external_api_url, json={
            'userId': user_id,
            'userName': user.get('UserName'),
            'email': user.get('Emails', [{}])[0].get('Value'),
            'displayName': user.get('DisplayName')
        })
        
    except Exception as e:
        print(f"Error: {e}")
    
    return {'statusCode': 200}
```

---

## ⚠️ 注意事项

### 1. CloudTrail 延迟
- CloudTrail 事件通常在 5-15 分钟内可用
- 不适合需要实时响应的场景

### 2. 敏感信息隐藏
- CloudTrail 会隐藏敏感信息（用户名、邮箱等）
- 需要通过 Identity Store API 获取完整用户信息

### 3. SCIM Token 轮换
- 如果 SCIM token 是在 2024年9月之前创建的，需要轮换才能看到 CloudTrail 事件
- 参考：[Rotate an access token](https://docs.aws.amazon.com/singlesignon/latest/userguide/rotate-token.html)

### 4. 成本考虑
- CloudTrail 事件存储有成本
- Lambda 调用有成本
- 建议设置合理的过滤规则

---

## 📚 参考文档

- [EventBridge Integration with IAM Identity Center](https://docs.aws.amazon.com/singlesignon/latest/userguide/eventbridge-integration.html)
- [Logging SCIM API calls with CloudTrail](https://docs.aws.amazon.com/singlesignon/latest/userguide/scim-logging-using-cloudtrail.html)
- [EventBridge Event Patterns](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-event-patterns.html)
- [SCIM API Reference](https://docs.aws.amazon.com/singlesignon/latest/developerguide/what-is-scim.html)

---

## ✅ 总结

**EventBridge 完全可以监听 SCIM 同步的用户创建事件并触发 Lambda！**

关键要点：
1. ✅ SCIM API 调用会记录到 CloudTrail
2. ✅ EventBridge 可以监听 CloudTrail 事件
3. ✅ 支持所有 SCIM 操作（CreateUser, PatchUser, DeleteUser 等）
4. ✅ 可以触发 Lambda、SNS、Step Functions 等服务
5. ⚠️ 注意 CloudTrail 延迟（5-15分钟）
6. ⚠️ 敏感信息被隐藏，需要额外 API 调用获取

这是一个完全可行的自动化方案！
