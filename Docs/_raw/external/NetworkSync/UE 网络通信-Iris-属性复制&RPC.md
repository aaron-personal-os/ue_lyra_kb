# 属性同步

---

UReplicationSystem::PreSendUpdate
UReplicationSystem::SendUpdate

UDataStreamChannel::ReceivedBunch
FReplicationReader::DispatchStateData(分发数据)

## DS端

---

> 💡
>
> 发包时先执行FReplicationSystemImpl的QuantizeDirtyStateData量化脏属性(**Quantize**)，再执行写操作(FReplicationWriter::WriteObjects)序列化属性数据(**Serialize**)到网络包

![image.png](http://pic.xyyxr.cn/20260504161046199.png)

![image.png](http://pic.xyyxr.cn/20260504161046200.png)

> 💡
>
> 收包先执行读取操作(FReplicationReader::ReadObjects)从网络包反序列化(**Deserialize**)属性数据，再分发数据(FReplicationReader::DispatchStateData)执行反量化(**Dequantize)，**最后执行对应的OnRep调用

![image.png](http://pic.xyyxr.cn/20260504161046201.png)

![image.png](http://pic.xyyxr.cn/20260504161046202.png)

![image.png](http://pic.xyyxr.cn/20260504161046203.png)

## 轮询需要发送的脏数据

---

PollReplicatedState

![轮询需要发送的脏数据(哪些字段发生了修改)](http://pic.xyyxr.cn/20260504161046204.png)

轮询需要发送的脏数据(哪些字段发生了修改)

## 量化属性数据

---

Gameplay和复制系统之间拷贝要复制的脏数据。

FStructNetSerializer::Quantize

 FObjectNetSerializerBase<T>::Quantize

![image.png](http://pic.xyyxr.cn/20260504161046199.png)

## 自定义网络复制

---

Iris的自定义属性同步相对旧版网络复制的自定义属性同步稍微复杂一点

参照:

FGameplayEffectContextHandleNetSerializer

FGameplayEffectContextNetSerializer

StructNetSerializer.cpp

## FastArray

---

# RPC

---

FNetRPC::Create/FNetRPC::CallFunction

![发送RPC FNetRPC::Create](http://pic.xyyxr.cn/20260504161046205.png)

发送RPC FNetRPC::Create

![接收RPC FNetRPC::CallFunction](http://pic.xyyxr.cn/20260504161048534.png)

接收RPC FNetRPC::CallFunction

# 网络复制裁剪

---

FReplicationFiltering

# F类的指针复制

After:TPolymorphicStructNetSerializerImpl