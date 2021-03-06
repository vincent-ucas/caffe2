#pragma once

#include "fbcollective/barrier.h"

namespace fbcollective {

class BarrierAllToOne : public Barrier {
 public:
  explicit BarrierAllToOne(
      const std::shared_ptr<Context>& context,
      int rootRank = 0)
      : Barrier(context), rootRank_(rootRank) {
    if (this->contextRank_ == rootRank_) {
      // Create send/recv buffers for every peer
      for (int i = 0; i < this->contextSize_; i++) {
        // Skip self
        if (i == this->contextRank_) {
          continue;
        }

        auto& pair = this->getPair(i);
        auto sdata = std::unique_ptr<int>(new int);
        auto sbuf = pair->createSendBuffer(1, sdata.get(), sizeof(int));
        sendBuffersData_.push_back(std::move(sdata));
        sendBuffers_.push_back(std::move(sbuf));
        auto rdata = std::unique_ptr<int>(new int);
        auto rbuf = pair->createRecvBuffer(0, rdata.get(), sizeof(int));
        recvBuffersData_.push_back(std::move(rdata));
        recvBuffers_.push_back(std::move(rbuf));
      }
    } else {
      // Create send/recv buffers to/from the root
      auto& pair = this->getPair(rootRank_);
      auto sdata = std::unique_ptr<int>(new int);
      auto sbuf = pair->createSendBuffer(0, sdata.get(), sizeof(int));
      sendBuffersData_.push_back(std::move(sdata));
      sendBuffers_.push_back(std::move(sbuf));
      auto rdata = std::unique_ptr<int>(new int);
      auto rbuf = pair->createRecvBuffer(1, rdata.get(), sizeof(int));
      recvBuffersData_.push_back(std::move(rdata));
      recvBuffers_.push_back(std::move(rbuf));
    }
  }

  void Run() {
    if (this->contextRank_ == rootRank_) {
      // Wait for message from all peers
      for (auto& b : recvBuffers_) {
        b->waitRecv();
      }
      // Notify all peers
      for (auto& b : sendBuffers_) {
        b->send();
      }
    } else {
      // Send message to root
      sendBuffers_[0]->send();
      // Wait for acknowledgement from root
      recvBuffers_[0]->waitRecv();
    }
  }

 protected:
  const int rootRank_;

  std::vector<std::unique_ptr<int>> sendBuffersData_;
  std::vector<std::unique_ptr<transport::Buffer>> sendBuffers_;
  std::vector<std::unique_ptr<int>> recvBuffersData_;
  std::vector<std::unique_ptr<transport::Buffer>> recvBuffers_;
};

} // namespace fbcollective
